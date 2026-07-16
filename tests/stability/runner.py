import asyncio
import time
import logging
import os
from typing import Dict, Any, List

from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from models.health import ProviderHealthManager
from models.router import ModelRouter
from kernel.bus import EventBus
from memory.manager import MemoryManager

from tests.chaos.injector import ChaosInjector
from tests.stability.monitor import StabilityMonitor

logger = logging.getLogger("stability_runner")

class StabilityRunner:
    """Executes massive volumes of workflows to test OS stability."""
    
    def __init__(self):
        self.health = ProviderHealthManager()
        self.router = ModelRouter(self.health)
        self.bus = EventBus()
        # Use an isolated cache for stability runs to check file growth
        self.memory = MemoryManager(cache_dir="workspace/stability_cache")
        self.scheduler = RuntimeScheduler(router=self.router, event_bus=self.bus, memory_manager=self.memory)
        self.monitor = StabilityMonitor()

    async def execute_batch(self, count: int, concurrent: bool = False) -> Dict[str, Any]:
        """Runs `count` workflows sequentially or concurrently.
        
        Returns a metrics report mapping execution stats.
        """
        # Ensure EventBus and Health are started
        await self.bus.start()
        await self.health.start()
        
        # Build 10,000 identical plans
        plans = []
        for i in range(count):
            tcb = TaskControlBlock(
                workflow_id=f"stab-wf-{i}",
                assigned_runtime="STANDARD",
                primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
            )
            node = WorkflowNode(node_id="node_1", dependencies=[], tcb=tcb)
            plan = WorkflowPlan(workflow_id=f"stab-wf-{i}", nodes={"node_1": node})
            plans.append(plan)

        # Warm up lazy imports, logging handlers, and pools before taking the baseline memory measurement
        warmup_tcb = TaskControlBlock(
            workflow_id="warmup-wf",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
        )
        warmup_node = WorkflowNode(node_id="node_1", dependencies=[], tcb=warmup_tcb)
        warmup_plan = WorkflowPlan(workflow_id="warmup-wf", nodes={"node_1": warmup_node})
        try:
            await self.scheduler.schedule_workflow(warmup_plan, [["node_1"]])
        except Exception:
            pass

        self.monitor.start_baseline()
        start_time = time.time()
        
        sim_flags = {
            "chaos_network_latency": True,
            "latency_ms": 1 # 1ms mock response
        }
        
        success_count = 0
        error_count = 0
        latencies = []
        
        async def run_single(plan: WorkflowPlan):
            nonlocal success_count, error_count
            t0 = time.time()
            try:
                await self.scheduler.schedule_workflow(plan, [["node_1"]])
                success_count += 1
                latencies.append(time.time() - t0)
            except Exception as e:
                logger.error(f"Workflow {plan.workflow_id} failed: {e}")
                error_count += 1

        with ChaosInjector(sim_flags):
            if concurrent:
                # Run in massive concurrent batches (limited by Semaphores inside scheduler anyway)
                batch_size = 100
                for i in range(0, len(plans), batch_size):
                    batch = plans[i:i+batch_size]
                    tasks = [asyncio.create_task(run_single(p)) for p in batch]
                    await asyncio.gather(*tasks)
            else:
                # Sequential
                for p in plans:
                    await run_single(p)

        total_time = time.time() - start_time
        
        # Capture snapshot
        snapshot = self.monitor.take_snapshot(count)
        
        # Cleanup
        await self.bus.stop()
        await self.health.stop()
        self.monitor.stop()
        
        # Check files in cache
        try:
            cache_files = os.listdir(self.memory.cache_dir)
            checkpoint_count = len(cache_files)
        except Exception:
            checkpoint_count = 0

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "execution_mode": "concurrent" if concurrent else "sequential",
            "total_executed": count,
            "success_count": success_count,
            "error_count": error_count,
            "total_time_sec": total_time,
            "avg_latency_sec": avg_latency,
            "memory_growth_kb": snapshot["memory_growth_kb"],
            "task_growth": snapshot["task_growth"],
            "checkpoint_count": checkpoint_count,
            "warnings": self.monitor.detect_leaks()
        }
