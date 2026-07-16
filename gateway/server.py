"""System Call Gateway FastAPI Server.

Orchestrates session validation, compilation, policy checks, scheduling,
runtimes dispatching, and sanitization formatting.
"""

import asyncio
import os
import logging
import uuid
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles

# Subsystem Imports
import config
from kernel.bus import EventBus
from kernel.registry import AgentRegistry
from kernel.lifecycle import LifecycleManager
from storage.checkpoints import CheckpointManager
from memory.manager import MemoryManager
from memory.context import ContextManager
from storage.conversations import ConversationManager
from compiler.compiler import AICompiler
from compiler.planner import ExecutionPlanner, CostOptimizer
from compiler.policy import PolicyEngine
from models.health import ProviderHealthManager
from models.router import ModelRouter
from runtime.factory import EnvironmentFactory
from runtime.tool_manager import ToolManager
from runtime.scheduler import RuntimeScheduler


# Gateway and UI Interfaces
from gateway.request_manager import RequestManager as SessionRequestManager
from gateway.formatter import ResponseFormatter
from ui.observability import ObservabilityService
from ui.analytics import RuntimeAnalytics
from contracts.message import EventMessage
from auth.routes import router as auth_router
from memory.semantic_cache import SemanticCache
from memory.context_compressor import ContextCompressor
from optimizer.pii_scrubber import PIIScrubber
from optimizer.cost_engine import CostEngine
from optimizer.model_selector import ModelSelector

logger = logging.getLogger("neelvak_kernel")

# =====================================================================
# GLOBAL STATE INITIALIZATION
# =====================================================================
event_bus = EventBus()
agent_registry = AgentRegistry()
lifecycle_manager = LifecycleManager()
checkpoint_manager = CheckpointManager()
memory_manager = MemoryManager(event_bus=event_bus)
context_manager = ContextManager()
conversation_manager = ConversationManager()
semantic_cache = SemanticCache(ttl_seconds=7200, similarity_threshold=0.75)
context_compressor = ContextCompressor(window_size=3, max_context_tokens=2000)
pii_scrubber = PIIScrubber()
cost_engine = CostEngine()
model_selector = ModelSelector()

# API Keys lookup for compiler
api_key_groq = os.getenv("GROQ_API_KEY", "")
api_key_or = os.getenv("OPENROUTER_API_KEY", "")
compiler = AICompiler(api_key_groq=api_key_groq, api_key_or=api_key_or, event_bus=event_bus)

planner = ExecutionPlanner()
cost_optimizer = CostOptimizer()
policy_engine = PolicyEngine()
health_manager = ProviderHealthManager()
model_router = ModelRouter(health_manager, event_bus)
environment_factory = EnvironmentFactory()
tool_manager = ToolManager(event_bus)

# Scheduler with injected dependencies for dynamic runtime construction
scheduler = RuntimeScheduler(
    router=model_router,
    event_bus=event_bus,
    memory_manager=memory_manager
)

session_manager = SessionRequestManager()
response_formatter = ResponseFormatter()
observability = ObservabilityService(event_bus)
analytics = RuntimeAnalytics()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI server."""
    # Boots up background loops, queues, and event buses
    await event_bus.start()
    await health_manager.start()
    tool_manager.start()
    
    from contracts.message import EventMessage
    await event_bus.publish(EventMessage(
        sender_id="GATEWAY",
        workflow_id="SYSTEM",
        receiver_id="EVENT",
        msg_type="EVENT",
        event_name="Kernel Started",
        payload={"status": "mounted"}
    ))
    
    logger.info("System Call Gateway core dependencies mounted.")
    
    yield
    
    # Recycles active connections and shuts down daemons
    await event_bus.stop()
    await health_manager.stop()
    tool_manager.stop()
    logger.info("System Call Gateway core dependencies unmounted.")

app = FastAPI(title="Neelvak AIOS System Call Gateway v1.3", lifespan=lifespan)

# Static web index location (React dist)
INDEX_HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist", "index.html")

# Mount assets
app.mount("/assets", StaticFiles(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist", "assets")), name="assets")

# Mount auth routes
app.include_router(auth_router)

class ChatRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the front-end dashboard UI statically."""
    try:
        async with aiofiles.open(INDEX_HTML_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend static UI frontend/dist/index.html not found.")

@app.get("/api/cache/stats")
async def cache_stats():
    """Returns semantic cache and context compressor analytics."""
    return {
        "semantic_cache": semantic_cache.get_stats(),
        "context_compressor": context_compressor.get_stats()
    }

@app.get("/api/conversations")
async def list_conversations():
    return {"conversations": conversation_manager.list_conversations()}

@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = conversation_manager.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@app.get("/api/stream/{conv_id}")
async def stream_events(conv_id: str):
    async def event_generator():
        q = asyncio.Queue()
        async def callback(msg):
            # Only push events for this conversation/workflow if needed. For now, push all or filter by ID.
            if msg.workflow_id == conv_id or msg.workflow_id == "BROADCAST":
                await q.put(msg)
        
        # Subscribe
        event_bus.subscribe("BROADCAST", callback)
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg.model_dump_json()}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe("BROADCAST", callback)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, req_raw: Request):
    """Processes user intent gateway calls through the complete microkernel pipeline."""
    # Obtain user session identifier (fallback to host IP)
    session_id = req_raw.client.host if req_raw.client else "unknown_session"
    
    # 1. Enforce Rate Limiting & Validation Checks
    payload_dict = request.model_dump()
    allowed, detail, sanitized_payload = session_manager.validate_request(payload_dict, session_id)
    if not allowed:
        if "Payload" in detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=429, detail=detail)
    
    prompt = sanitized_payload.get("prompt", request.prompt)
    
    conv_id = request.conversation_id

    if not conv_id:
        conv_id = conversation_manager.create_conversation()["id"]

    logger.info(f"Gateway: Received intent prompt: '{prompt}' for conversation {conv_id}")
    telemetry_logs = []

    # 1.5 PII Scrubbing Layer (Zero-Trust Local Execution)
    scrubbed_prompt, pii_map = pii_scrubber.scrub(prompt)
    if pii_map:
        telemetry_logs.append(f"[Kernel] PII Scrubber detected and masked {len(pii_map)} sensitive entities locally.")
        prompt = scrubbed_prompt
        
    try:
        # 2a. Semantic Cache Check (org-scoped, runs BEFORE L1-L5 cache)
        org_id = req_raw.headers.get("X-Org-Id", "global")
        sc_hit, sc_response, sc_score = semantic_cache.query(prompt, org_id=org_id)
        if sc_hit and sc_response:
            telemetry_logs.append(f"[Kernel] Semantic Cache HIT (similarity: {sc_score:.2f}). Zero-cost short-circuit.")
            telemetry_logs.append("[Kernel] Bypassed compiler, policy, scheduler, and runtime phases entirely.")
            payload = {
                "conversation_id": conv_id,
                "winner": "SemanticCache",
                "tier": "CACHED (Zero Cost)",
                "processes": [
                    {"id": "PCB_SEMANTIC", "role": "Semantic Cache", "state": "TERMINATED", "model": "SemanticCache", "provider": "internal"}
                ],
                "telemetry": telemetry_logs,
                "output": sc_response,
                "cached": True
            }
            conversation_manager.append_turn(conv_id, prompt, payload)
            return payload

        # 2b. Check L1-L5 Cache Subsystem (Short-circuiting evaluation)
        hit, cached_val, css = memory_manager.check_cache_hit(prompt, "STANDARD")
        if hit and cached_val:
            telemetry_logs.append(f"[Kernel] Cache Hit resolved on prompt (CSS: {css:.2f}). Short-circuiting execution.")
            telemetry_logs.append("[Kernel] MemoryManager promoted cached payload metadata.")
            
            scrubbed = response_formatter.clean_output(cached_val)
            analytics.record_transaction("cache_hit", 0, 0.0, 1.0, False)
            
            # Also store in semantic cache for cross-employee benefit
            semantic_cache.store(prompt, scrubbed, org_id=org_id)
            
            payload = {
                "conversation_id": conv_id,
                "winner": "MemoryManager Cache",
                "tier": "RETRIEVAL TIER",
                "processes": [
                    {"id": "PCB_CACHE", "role": "Cache Manager", "state": "TERMINATED", "model": "L1-L5 Cache hit", "provider": "internal"}
                ],
                "telemetry": telemetry_logs,
                "output": scrubbed
            }
            conversation_manager.append_turn(conv_id, prompt, payload)
            return payload
        # 3. Context Compression Phase
        # Retrieve raw history for this conversation
        raw_history = []
        conv_obj = conversation_manager.get_conversation(conv_id)
        if conv_obj and "turns" in conv_obj:
            for turn in conv_obj["turns"]:
                raw_history.append({"role": "user", "content": turn.get("user", "")})
                raw_history.append({"role": "system", "content": turn.get("agent_response", {}).get("output", "")})
        
        # Compress the history
        compressed_context, orig_tokens, comp_tokens = context_compressor.compress(raw_history)
        if compressed_context:
            telemetry_logs.append(f"[Kernel] Context compressed: {orig_tokens} tokens → {comp_tokens} tokens (saved {orig_tokens - comp_tokens}).")
            prompt = f"{compressed_context}\n\nCurrent Prompt:\n{prompt}"

        # 3.5 Cost Optimization Engine
        # Generate 4-Score CSS Profile to drive model selection (prototype logging)
        css_profile = cost_engine.evaluate(prompt, token_estimate=comp_tokens + 50)
        telemetry_logs.append(f"[Kernel] CostEngine generated CSS Profile: Cost={css_profile['cost']}, Complexity={css_profile['complexity']}, Lane={css_profile['lane']}")
        # Select optimal model
        opt_provider, opt_model, opt_tier = model_selector.select(css_profile)
        telemetry_logs.append(f"[Kernel] ModelSelector routed execution to: {opt_provider}/{opt_model} ({opt_tier})")

        # 4. Compiler Phase (10 sequential passes building WorkflowPlan)
        plan = await compiler.compile(prompt, workflow_id=conv_id)
        
        await event_bus.publish(EventMessage(
            sender_id="COMPILER",
            workflow_id=plan.workflow_id,
            receiver_id="EVENT",
            msg_type="EVENT",
            event_name="WorkflowPlan",
            payload={"plan": plan.model_dump()}
        ))
        
        telemetry_logs.append(f"[Kernel] Multi-pass compilation successful. Created WorkflowPlan {plan.workflow_id}.")

        # 4. Policy Engine Compliance Sweep
        policy_passed, policy_msg = policy_engine.validate_plan(plan, prompt)
        
        await event_bus.publish(EventMessage(
            sender_id="POLICY_ENGINE",
            workflow_id=plan.workflow_id,
            receiver_id="EVENT",
            msg_type="EVENT",
            event_name="Policy Validation",
            payload={"policy_passed": policy_passed, "policy_msg": policy_msg}
        ))
        
        if not policy_passed:
            telemetry_logs.append(f"[Kernel] ONLINE -> WORKFLOW FAILED -> Await next request -> ONLINE")
            telemetry_logs.append(f"[WORKFLOW FAILED] Reason: Policy Violation alert - {policy_msg}")
            telemetry_logs.append("[Recovery] Await next request")
            payload = {
                "conversation_id": conv_id,
                "workflow_id": plan.workflow_id,
                "winner": "WORKFLOW FAILED",
                "tier": "WORKFLOW FAILED",
                "processes": [],
                "telemetry": telemetry_logs,
                "output": f"Execution Aborted by Security Policy Ring: {policy_msg}\nRecovery Action: Await next request",
                "metadata": {}
            }
            conversation_manager.append_turn(conv_id, prompt, payload)
            return payload

        # 5. Cost Optimization Adjustments
        # Simulate remaining budget check
        cost_optimizer.optimize_plan_budgets(plan, remaining_budget=0.05)

        # 6. Environment Container Provisioning
        container_info = environment_factory.provision_container(plan.workflow_id)
        telemetry_logs.append(f"[Kernel] Provisioned workspace environment container at: {container_info['root']}")

        # 7. Execution Planning (DAG sorting) and Scheduling
        layers = planner.plan_execution_layers(plan)
        
        await event_bus.publish(EventMessage(
            sender_id="PLANNER",
            workflow_id=plan.workflow_id,
            receiver_id="EVENT",
            msg_type="EVENT",
            event_name="Planner Completed",
            payload={"layers": len(layers)}
        ))
        
        # Flatten dict format from ExecutionPlanner into List[List[str]] for scheduler
        execution_layers: List[List[str]] = [layer["nodes"] for layer in layers]
        telemetry_logs.append(f"[Kernel] Topological sort completed. Layers count: {len(execution_layers)}.")
        
        # Populate Agent Registry process table for visual updates
        runtime_selection_report = []
        for node_id, node in plan.nodes.items():
            decision = model_router.resolve_capability(
                node.tcb.primary_capability, plan.workflow_id
            )
            prov = decision.selected_provider
            model_name = decision.selected_model
            routing_chain = decision.routing_chain
            runtime_selection_report.append({
                "intent": prompt[:50] + "..." if len(prompt) > 50 else prompt,
                "complexity": node.tcb.primary_capability.minimum_reasoning_tier,
                "chosen_runtime": node.tcb.assigned_runtime,
                "reason": f"Matched capability constraints for tier: {node.tcb.primary_capability.minimum_reasoning_tier}",
                "confidence": "98%"
            })
            await agent_registry.register(node_id, {
                "role": f"{node.tcb.primary_capability.minimum_reasoning_tier} Node",
                "runtime": node.tcb.assigned_runtime,
                "workflow_node": node_id,
                "provider": prov,
                "model": model_name,
                "current_task": prompt[:20] + "...",
                "status": "QUEUED",
                "retries": 0,
                "execution_time_ms": 0.0,
                "current_state": "QUEUED",
                "parent_id": plan.workflow_id
            })

        # Run scheduler loops
        # Hook up state updating events during runtime execution
        for node_list in execution_layers:
            for node_id in node_list:
                await agent_registry.update_state(node_id, "EXECUTING")
                telemetry_logs.append(f"[Kernel] Executing TCB node {node_id} on {plan.nodes[node_id].tcb.assigned_runtime} runtime.")

        scheduler_results = await scheduler.schedule_workflow(plan, execution_layers)
        
        # Mark terminated in registry
        for node_id in plan.nodes.keys():
            await agent_registry.update_state(node_id, "TERMINATED")
                
        # 8. Retrieve Output and Calibrate Analytics
        # Select main output result from last node layer, skipping verification nodes
        last_node_id = ""
        for layer in reversed(execution_layers):
            for n_id in layer:
                # Fetch task name if present
                task_name = plan.nodes[n_id].tcb.payload.get("task_name", "").lower()
                # Determine if this node is a verification step by checking both task name and node identifier
                if ("verify" not in task_name) and ("fallback" not in task_name) and ("verify" not in n_id.lower()):
                    last_node_id = n_id
                    break
            if last_node_id:
                break
        
        # Fallback to the very last node if no suitable non‑verification node was found
        if not last_node_id and execution_layers:
            last_node_id = execution_layers[-1][0]

        node_result = scheduler_results.get(last_node_id)
        
        if node_result:
            await event_bus.publish(EventMessage(
                sender_id="FORMATTER",
                workflow_id=plan.workflow_id,
                receiver_id="EVENT",
                msg_type="EVENT",
                event_name="Formatter Started",
                payload={"stage": "sanitization"}
            ))
            formatted = response_formatter.format_runtime_result(node_result)
            clean_output = formatted["output"]
            metadata = formatted["metadata"]
            await event_bus.publish(EventMessage(
                sender_id="FORMATTER",
                workflow_id=plan.workflow_id,
                receiver_id="EVENT",
                msg_type="EVENT",
                event_name="Formatter Completed",
                payload={"stage": "sanitization"}
            ))
            winner = getattr(node_result, "winner", "N/A")
        else:
            winner = "N/A"
            clean_output = "No execution output returned."
            metadata = {}

        # 8.5 PII Restoration Layer
        if pii_map:
            clean_output = pii_scrubber.restore(clean_output, pii_map)
            telemetry_logs.append("[Kernel] PII Scrubber safely restored masked sensitive entities into final output.")

        # Store cache
        memory_manager.store_cache(prompt, clean_output, scope="L2")
        # Also store in semantic cache for org-wide cross-employee benefit
        semantic_cache.store(prompt, clean_output, org_id=org_id)

        # Record analytics metrics
        analytics.record_transaction(
            workflow_id=plan.workflow_id,
            tokens=1500,
            cost=metadata.get("estimated_cost_usd", 0.0),
            latency_ms=metadata.get("latency_ms", 0.0),
            error_occured=False
        )
        
        # 9. Clean up environments
        environment_factory.deprovision_container(plan.workflow_id)
        telemetry_logs.append("[Kernel] Deprovisioned sandbox container. Resources released.")

        # 10. Compile dashboard processes
        processes = []
        reg_items = await agent_registry.get_all()
        for item in reg_items:
            if item["parent_id"] == plan.workflow_id:
                processes.append({
                    "id": item["agent_id"],
                    "role": f"Node Task - {item['runtime']}",
                    "state": item["state"],
                    "model": item["model"],
                    "provider": item["provider"]
                })
                # Clean up processes table from memory after compiling
                await agent_registry.remove(item["agent_id"])

        # Fallback default if process table was empty
        if not processes:
            processes = []

        is_loopback = "[KERNEL_LOOPBACK_RECOVERY]" in clean_output
        if is_loopback:
            telemetry_logs.append("[Telemetry] Degraded Mode: Running on Kernel Loopback Storage")

        payload = {
            "conversation_id": conv_id,
            "workflow_id": plan.workflow_id,
            "winner": winner,
            "tier": "COMPETITIVE TIER" if winner != "N/A" else "STANDARD TIER",
            "processes": processes,
            "telemetry": telemetry_logs,
            "output": clean_output,
            "metadata": metadata,
            "runtime_selection": runtime_selection_report,
            "sandbox_amber": is_loopback
        }
        
        await event_bus.publish(EventMessage(
            sender_id="GATEWAY",
            workflow_id=plan.workflow_id,
            receiver_id="EVENT",
            msg_type="EVENT",
            event_name="Workflow Completed",
            payload={"latency_ms": metadata.get("latency_ms", 0.0)}
        ))
        await event_bus.publish(EventMessage(
            sender_id="GATEWAY",
            workflow_id=plan.workflow_id,
            receiver_id="EVENT",
            msg_type="EVENT",
            event_name="Gateway Returned",
            payload={"status": "success"}
        ))
        
        conversation_manager.append_turn(conv_id, prompt, payload)
        return payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Systemic Gateway Error: {e}", exc_info=True)
        # Attempt to deprovision container if plan is bound
        try:
            if 'plan' in locals() and plan:
                environment_factory.deprovision_container(plan.workflow_id)
        except Exception:
            pass

        e_str = str(e).lower()
        e_type = type(e).__name__.lower()
        
        # 1. PROVIDER TIMEOUT
        if "timeout" in e_str or "timeout" in e_type or "connecterror" in e_type or "network" in e_str or "network" in e_type or isinstance(e, asyncio.TimeoutError):
            status = "PROVIDER TIMEOUT"
            recovery = "Hot Swap Attempt / Router Failover"
        # 2. WORKFLOW FAILED
        elif "policy" in e_str or "compil" in e_str or "compil" in e_type or "cyclic dependency" in e_str or "plan validation" in e_str or "valueerror" in e_type:
            status = "WORKFLOW FAILED"
            recovery = "Await next request"
        # 3. RUNTIME ERROR
        elif "runtime" in e_str or "runtime" in e_type or "worker" in e_str or "looper" in e_str or "scheduler" in e_str:
            status = "RUNTIME ERROR"
            recovery = "Recovery policy executes"
        # 4. KERNEL PANIC
        else:
            status = "KERNEL PANIC"
            recovery = "System Reboot Required"

        telemetry_logs.append(f"[Kernel] ONLINE -> {status} -> {recovery} -> ONLINE")

        payload = {
            "conversation_id": conv_id,
            "winner": status,
            "tier": status,
            "processes": [],
            "telemetry": telemetry_logs + [f"[{status}] Reason: {str(e)}", f"[Recovery] {recovery}"],
            "output": f"Execution Interrupted: {status}\nReason: {str(e)}\nRecovery Action: {recovery}",
            "metadata": {}
        }
        if 'plan' in locals() and plan:
            payload["workflow_id"] = plan.workflow_id
            
        conversation_manager.append_turn(conv_id, prompt, payload)
        return payload

@app.post("/api/analytics/approve")
async def approve_analytics():
    """Promotes staged optimization weights (Human Approval Gate)."""
    analytics.compute_optimization_vectors()
    success = analytics.approve_pending_calibrations()
    if success:
        return {"status": "success", "message": "Staged compiler weights successfully promoted.", "active_weights": analytics.active_weights}
    else:
        return {"status": "error", "message": "No pending calibrations found to promote."}

@app.get('/{full_path:path}', response_class=HTMLResponse)
async def catch_all(full_path: str):
    try:
        async with aiofiles.open(INDEX_HTML_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='Frontend not found.')
