"""Neelvak AIOS Unified Bootstrapper.

Coordinates platform initialization, validates environment configurations,
and boots dual-transports (MCP & ASGI).
"""

import os
import sys
import logging
import json
from typing import Any, Dict
from dotenv import load_dotenv

# Mount local .env variables securely before execution layers boot
load_dotenv()

# Setup professional system-level streaming logging configurations
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [Neelvak-AIOS-Kernel] - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("neelvak_kernel")

# =====================================================================
# HARD KERNEL KEY VALIDATION RING (Fail Loud, Fail Early)
# =====================================================================
_GROQ_KEY: str = os.getenv("GROQ_API_KEY", "")
_OR_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

if not _GROQ_KEY or "your_" in _GROQ_KEY or len(_GROQ_KEY.strip()) < 10:
    logger.critical("Fatal: GROQ_API_KEY is missing or invalid in the local .env structure.")
    sys.exit(1)

if not _OR_KEY or "your_" in _OR_KEY or len(_OR_KEY.strip()) < 10:
    logger.critical("Fatal: OPENROUTER_API_KEY is missing or invalid in the local .env structure.")
    sys.exit(1)

# =====================================================================
# DUAL-TRANSPORT BOOTSTRAP SUBSYSTEM (CLI / PROTOCOL OVERRIDES)
# =====================================================================

def create_mcp_server() -> Any:
    """Instantiates the native Model Context Protocol server.

    Returns:
        FastMCP server instance.
    """
    try:
        from fastmcp import FastMCP
        from gateway.server import (
            compiler, policy_engine, environment_factory, planner, 
            model_router, agent_registry, scheduler, memory_manager, 
            response_formatter, analytics, event_bus, health_manager, tool_manager,
            checkpoint_manager, conversation_manager
        )
    except ImportError as exc:
        raise ImportError(f"Failed to import kernel dependencies: {exc}")

    mcp_server = FastMCP("Neelvak-AIOS")

    @mcp_server.tool()
    async def execute_neelvak_agent_matrix(prompt: str) -> str:
        """Executes a prompt intent string across the complete microkernel execution runtime matrix.

        Args:
            prompt: The user query or workflow request.

        Returns:
            A string showing results of the agent execution.
        """
        # Ensure kernel background systems are active
        if not event_bus._running:
            await event_bus.start()
            await health_manager.start()
            tool_manager.start()

        try:
            # 1. Compile Phase (10-pass)
            plan = await compiler.compile(prompt, workflow_id=workflow_id)
            
            await event_bus.publish(EventMessage(
                sender_id="COMPILER",
                workflow_id=plan.workflow_id,
                receiver_id="EVENT",
                msg_type="EVENT",
                event_name="WorkflowPlan",
                payload={"plan": plan.model_dump()}
            ))
            
            telemetry_logs.append(f"[Kernel] Multi-pass compilation successful. Created WorkflowPlan {plan.workflow_id}.")
            
            policy_passed, policy_msg = policy_engine.validate_plan(plan, prompt)
            
            if not policy_passed:
                return f"Execution Aborted by Security Policy Ring: {policy_msg}"
            
            # 2. Workspace & Topological Planning
            environment_factory.provision_container(plan.workflow_id)
            layers = planner.plan_execution_layers(plan)
            execution_layers = [layer["nodes"] for layer in layers]
            
            # 3. Dynamic Capability Routing & Registry Updates
            for node_id, node in plan.nodes.items():
                decision = model_router.resolve_capability(
                    node.tcb.primary_capability, plan.workflow_id
                )
                prov = decision.selected_provider
                model_name = decision.selected_model
                routing_chain = decision.routing_chain
                await agent_registry.register(node_id, {
                    "role": f"{node.tcb.primary_capability.minimum_reasoning_tier} Node",
                    "runtime": node.tcb.assigned_runtime,
                    "workflow_node": node_id,
                    "provider": prov,
                    "model": model_name,
                    "current_task": "Execute Workflow Node",
                    "status": "QUEUED",
                    "retries": 0,
                    "execution_time_ms": 0.0,
                    "current_state": "QUEUED",
                    "parent_id": plan.workflow_id
                })
            
            # 4. Orchestrate Executions (Catches graceful failure fallbacks natively)
            scheduler_results = await scheduler.schedule_workflow(plan, execution_layers)
            
            # 5. Cleanup & Format
            environment_factory.deprovision_container(plan.workflow_id)
            last_node_id = execution_layers[-1][0] if execution_layers else ""
            node_result = scheduler_results.get(last_node_id)
            
            if node_result:
                formatted = response_formatter.format_runtime_result(node_result)
                return formatted["output"]
                
            return "No execution output returned."
            
        except Exception as e:
            logger.error(f"Systemic MCP execution fault: {e}", exc_info=True)
            return f"Systemic MCP Error: {e}"

    @mcp_server.resource("neelvak://history")
    async def get_execution_history() -> str:
        """Retrieves historical checkpoint transaction maps from durable system storage adapters."""
        try:
            checkpoints = checkpoint_manager.list_checkpoints()
            history = []
            for cp_id in checkpoints:
                data = checkpoint_manager.load_checkpoint(cp_id)
                if data:
                    history.append(data)
            return json.dumps({"sessions": history, "notice": "Storage system active."})
        except Exception as e:
            logger.error(f"Failed to retrieve execution history: {e}")
            return json.dumps({"sessions": [], "notice": f"Storage system error: {e}"})

    return mcp_server

if __name__ == "__main__":
    if "--mcp" in sys.argv:
        logger.info("Initializing native Model Context Protocol over STDIO Transport Node...")
        try:
            mcp = create_mcp_server()
            mcp.run(transport="stdio")
        except ImportError as e:
            logger.critical(f"Initialization Aborted: Missing dependency fields. Error: {e}")
            print("[Fatal Kernel Error] Run pip install -r requirements.txt first.", file=sys.stderr)
            sys.exit(1)
    else:
        import uvicorn
        logger.info("Booting local ASGI framework mapping to Uvicorn Web Server Node...")
        uvicorn.run("gateway.server:app", host="127.0.0.1", port=8000, reload=True)
