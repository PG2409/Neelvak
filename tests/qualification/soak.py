import asyncio
import time
import logging
import gc
import os
import tracemalloc
from typing import Dict, Any, List

from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from models.health import ProviderHealthManager
from models.router import ModelRouter
from kernel.bus import EventBus
from memory.manager import MemoryManager
from tests.chaos.injector import ChaosInjector

logger = logging.getLogger("soak_qualification")

class SoakTester:
    """Executes a simulated multi-hour soak test containing various runtime executions."""

    def __init__(self, cycles: int = 1000):
        self.cycles = cycles
        self.health = ProviderHealthManager()
        self.router = ModelRouter(self.health)
        self.bus = EventBus()
        self.memory = MemoryManager(cache_dir="workspace/soak_cache")
        self.scheduler = RuntimeScheduler(router=self.router, event_bus=self.bus, memory_manager=self.memory)

    async def run_soak(self) -> Dict[str, Any]:
        """Runs the continuous soak validation."""
        logger.info("Initializing Soak Test components...")
        await self.bus.start()
        await self.health.start()

        tracemalloc.start()
        gc.collect()
        mem_start, _ = tracemalloc.get_traced_memory()
        start_time = time.time()

        runtimes = ["STANDARD", "COMPETITIVE", "MICRO", "DIRECT", "RETRIEVAL"]
        success_count = 0
        failure_count = 0
        latencies = []

        # Chaos sim flags to inject during soak test to ensure failovers work
        sim_flags = {
            "chaos_network_latency": True,
            "latency_ms": 1,
            "chaos_fs_write_fail": False,
        }

        # Build workflows
        plans = []
        for i in range(self.cycles):
            rt = runtimes[i % len(runtimes)]
            tcb = TaskControlBlock(
                workflow_id=f"soak-wf-{i}",
                assigned_runtime=rt,
                primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
            )
            node = WorkflowNode(node_id="node_1", dependencies=[], tcb=tcb)
            plan = WorkflowPlan(workflow_id=f"soak-wf-{i}", nodes={"node_1": node})
            plans.append(plan)

        async def execute_one(plan: WorkflowPlan):
            nonlocal success_count, failure_count
            t0 = time.time()
            try:
                await self.scheduler.schedule_workflow(plan, [["node_1"]])
                success_count += 1
                latencies.append(time.time() - t0)
            except Exception as e:
                logger.error(f"Soak task {plan.workflow_id} failed: {e}")
                failure_count += 1

        logger.info(f"Soak qualification: commencing execution of {self.cycles} cycles...")
        with ChaosInjector(sim_flags):
            batch_size = 50
            for idx in range(0, len(plans), batch_size):
                batch = plans[idx:idx + batch_size]
                tasks = [asyncio.create_task(execute_one(p)) for p in batch]
                await asyncio.gather(*tasks)
                # Yield to let tasks finish and loop cycle
                await asyncio.sleep(0.001)

        # Cleanup
        await self.bus.stop()
        await self.health.stop()
        gc.collect()
        
        mem_end, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        elapsed = time.time() - start_time
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

        metrics = {
            "cycles_run": self.cycles,
            "success": success_count,
            "failures": failure_count,
            "elapsed_sec": elapsed,
            "avg_latency_sec": avg_lat,
            "memory_growth_kb": (mem_end - mem_start) / 1024.0,
            "remaining_tasks": len(asyncio.all_tasks())
        }
        logger.info(f"Soak Test metrics compiled: {metrics}")
        return metrics

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(SoakTester(cycles=500).run_soak())
