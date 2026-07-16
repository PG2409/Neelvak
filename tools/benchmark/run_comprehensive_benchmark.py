import asyncio
import time
import json
import os
import sys
import statistics
import tracemalloc
from fastapi.testclient import TestClient

# Add workspace root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from kernel.bus import EventBus
from kernel.registry import AgentRegistry
from kernel.lifecycle import LifecycleManager
from storage.checkpoints import CheckpointManager
from memory.manager import MemoryManager
from memory.context import ContextManager
from compiler.compiler import AICompiler
from compiler.planner import ExecutionPlanner, CostOptimizer
from compiler.policy import PolicyEngine
from models.health import ProviderHealthManager
from models.router import ModelRouter
from runtime.factory import EnvironmentFactory
from runtime.tool_manager import ToolManager
from runtime.scheduler import RuntimeScheduler
from runtimes.competitive import CompetitiveRuntime
from runtimes.standard import StandardRuntime
from runtimes.micro import MicroRuntime
from runtimes.direct import DirectRuntime
from runtimes.retrieval import RetrievalRuntime
from gateway.request_manager import RequestManager
from gateway.server import app
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from contracts.message import EventMessage

def calc_stats(lats):
    if not lats:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0, "count": 0}
    lats.sort()
    n = len(lats)
    return {
        "p50": lats[int(n * 0.50)],
        "p90": lats[int(n * 0.90)],
        "p95": lats[int(n * 0.95)],
        "p99": lats[int(n * 0.99)],
        "max": max(lats),
        "min": min(lats),
        "avg": sum(lats) / n,
        "count": n
    }

async def main():
    print("Starting Comprehensive AIOS Subsystem Benchmarks...")
    tracemalloc.start()
    
    results = {}
    
    # 1. AI Compiler
    print("Benchmarking AI Compiler...")
    compiler = AICompiler(api_key_groq="mock-groq")
    lats = []
    plans = []
    t_start = time.process_time()
    for i in range(50):
        start = time.perf_counter()
        plan = await compiler.compile(f"Standard cognitive workflow benchmark intent query id {i}")
        lats.append(time.perf_counter() - start)
        plans.append(plan)
    results["compiler"] = calc_stats(lats)
    results["compiler"]["cpu_time_s"] = time.process_time() - t_start
    
    # 2. Policy Engine
    print("Benchmarking Policy Engine...")
    policy = PolicyEngine()
    lats = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        policy.validate_plan(plans[i % len(plans)], f"Verify prompt safety constraints query id {i}")
        lats.append(time.perf_counter() - start)
    results["policy_engine"] = calc_stats(lats)
    results["policy_engine"]["cpu_time_s"] = time.process_time() - t_start

    # 3. MemoryManager
    print("Benchmarking MemoryManager...")
    mem_mgr = MemoryManager()
    lats_store = []
    lats_check = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        mem_mgr.store_cache(f"key_{i}", f"val_{i}", scope="L1")
        lats_store.append(time.perf_counter() - start)
        
        start = time.perf_counter()
        mem_mgr.check_cache_hit(f"key_{i}", "STANDARD")
        lats_check.append(time.perf_counter() - start)
    results["memory_store"] = calc_stats(lats_store)
    results["memory_check"] = calc_stats(lats_check)
    results["memory_manager_cpu_time_s"] = time.process_time() - t_start

    # 4. Context Manager
    print("Benchmarking Context Manager...")
    ctx_mgr = ContextManager()
    lats = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        ctx_mgr.add_message("user", f"Context window content addition iteration {i}")
        ctx_mgr.pack_context()
        lats.append(time.perf_counter() - start)
    results["context_manager"] = calc_stats(lats)
    results["context_manager"]["cpu_time_s"] = time.process_time() - t_start

    # 5. ModelRouter
    print("Benchmarking ModelRouter...")
    health = ProviderHealthManager()
    router = ModelRouter(health)
    profile = CapabilityProfile(minimum_reasoning_tier="STANDARD", needs_vision=True)
    lats = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        router.resolve_capability(profile, f"wf_{i}")
        lats.append(time.perf_counter() - start)
        router.purge_workflow(f"wf_{i}")
    results["model_router"] = calc_stats(lats)
    results["model_router"]["cpu_time_s"] = time.process_time() - t_start

    # 6. ProviderHealthManager
    print("Benchmarking ProviderHealthManager...")
    lats = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        health.record_failure("groq")
        health.record_success("groq")
        health.get_status("groq")
        lats.append(time.perf_counter() - start)
    results["provider_health_manager"] = calc_stats(lats)
    results["provider_health_manager"]["cpu_time_s"] = time.process_time() - t_start

    # 7. CheckpointManager
    print("Benchmarking CheckpointManager...")
    chk_mgr = CheckpointManager()
    lats = []
    t_start = time.process_time()
    for i in range(50):
        start = time.perf_counter()
        chk_id = f"test_chk_{i}"
        key = await chk_mgr.create_checkpoint(chk_id, "wf_bench", "EXECUTING", {"param": i}, ["log1", "log2"])
        await chk_mgr.load_and_validate_checkpoint(key)
        await chk_mgr.adapter.delete(key)
        lats.append(time.perf_counter() - start)
    results["checkpoint_manager"] = calc_stats(lats)
    results["checkpoint_manager"]["cpu_time_s"] = time.process_time() - t_start

    # 8. Runtimes A-E
    print("Benchmarking Runtimes A-E...")
    bus = EventBus()
    await bus.start()
    
    # Runtime A - Competitive
    rt_a = CompetitiveRuntime(router=router)
    tcb_a = TaskControlBlock(workflow_id="wf_comp", assigned_runtime="COMPETITIVE", primary_capability=CapabilityProfile(minimum_reasoning_tier="HIGH"))
    lats = []
    for _ in range(50):
        start = time.perf_counter()
        await rt_a.validate(tcb_a)
        await rt_a.initialize({"task_name": "comp_task"})
        await rt_a.execute()
        await rt_a.cleanup()
        lats.append(time.perf_counter() - start)
    results["runtime_a_competitive"] = calc_stats(lats)

    # Runtime B - Standard
    rt_b = StandardRuntime(router=router, event_bus=bus)
    tcb_b = TaskControlBlock(workflow_id="wf_std", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))
    lats = []
    for _ in range(50):
        start = time.perf_counter()
        await rt_b.validate(tcb_b)
        await rt_b.initialize({"task_name": "std_task"})
        await rt_b.execute()
        await rt_b.cleanup()
        lats.append(time.perf_counter() - start)
    results["runtime_b_standard"] = calc_stats(lats)

    # Runtime C - Micro
    rt_c = MicroRuntime(router=router)
    tcb_c = TaskControlBlock(workflow_id="wf_micro", assigned_runtime="MICRO", primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD"))
    lats = []
    for _ in range(50):
        start = time.perf_counter()
        await rt_c.validate(tcb_c)
        await rt_c.initialize({"task_name": "micro_task"})
        await rt_c.execute()
        await rt_c.cleanup()
        lats.append(time.perf_counter() - start)
    results["runtime_c_micro"] = calc_stats(lats)

    # Runtime D - Direct
    rt_d = DirectRuntime(router=router)
    tcb_d = TaskControlBlock(workflow_id="wf_direct", assigned_runtime="DIRECT", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))
    lats = []
    for _ in range(50):
        start = time.perf_counter()
        await rt_d.validate(tcb_d)
        await rt_d.initialize({"task_name": "direct_task"})
        await rt_d.execute()
        await rt_d.cleanup()
        lats.append(time.perf_counter() - start)
    results["runtime_d_direct"] = calc_stats(lats)

    # Runtime E - Retrieval
    rt_e = RetrievalRuntime(memory_manager=mem_mgr)
    tcb_e = TaskControlBlock(workflow_id="wf_retrieval", assigned_runtime="RETRIEVAL", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))
    lats = []
    for _ in range(50):
        start = time.perf_counter()
        await rt_e.validate(tcb_e)
        await rt_e.initialize({"task_name": "retrieval_task"})
        await rt_e.execute()
        await rt_e.cleanup()
        lats.append(time.perf_counter() - start)
    results["runtime_e_retrieval"] = calc_stats(lats)

    await bus.stop()

    # 9. Gateway
    print("Benchmarking API Gateway...")
    lats = []
    t_start = time.process_time()
    with TestClient(app) as client:
        # Priming call
        client.post("/api/chat", json={"prompt": "warmup"})
        for i in range(50):
            start = time.perf_counter()
            client.post("/api/chat", json={"prompt": f"Benchmark request {i} - unique query"})
            lats.append(time.perf_counter() - start)
    results["gateway"] = calc_stats(lats)
    results["gateway"]["cpu_time_s"] = time.process_time() - t_start

    # 10. RequestManager
    print("Benchmarking RequestManager...")
    req_mgr = RequestManager()
    lats = []
    t_start = time.process_time()
    for i in range(100):
        start = time.perf_counter()
        req_mgr.validate_request(f"session_{i}")
        lats.append(time.perf_counter() - start)
    results["request_manager"] = calc_stats(lats)
    results["request_manager"]["cpu_time_s"] = time.process_time() - t_start

    # 11. ToolManager
    print("Benchmarking ToolManager...")
    bus = EventBus()
    await bus.start()
    tool_mgr = ToolManager(event_bus=bus, workspace_root="tests/tool_stress")
    tool_mgr.start()
    
    lats = []
    t_start = time.process_time()
    
    for i in range(100):
        msg = EventMessage(
            sender_id="TEST_CLIENT",
            receiver_id="TOOL_MANAGER",
            workflow_id="wf_tool_bench",
            msg_type="COMMAND",
            event_name="EXECUTE_TOOL",
            payload={"tool": "python_eval", "params": {"code": f"x = {i}"}, "tcb_id": f"TCB-{i}"}
        )
        start = time.perf_counter()
        await tool_mgr.handle_tool_call(msg)
        lats.append(time.perf_counter() - start)
        
    results["tool_manager"] = calc_stats(lats)
    results["tool_manager"]["cpu_time_s"] = time.process_time() - t_start
    tool_mgr.stop()
    await bus.stop()
    
    # 12. Memory Snapshot
    current, peak = tracemalloc.get_traced_memory()
    results["memory_usage"] = {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024
    }
    tracemalloc.stop()
    
    # Load Stress Metrics
    print("Loading stress test metrics...")
    stress_metrics_path = "tests/stress/reports/metrics.json"
    if os.path.exists(stress_metrics_path):
        with open(stress_metrics_path, "r") as f:
            stress_data = json.load(f)
        results["stress"] = stress_data
    else:
        results["stress"] = {}

    # Write output to reports/performance_metrics.json
    os.makedirs("reports", exist_ok=True)
    with open("reports/performance_metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print("Comprehensive Performance Benchmarking Complete.")

if __name__ == "__main__":
    asyncio.run(main())
