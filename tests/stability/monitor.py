import tracemalloc
import asyncio
import gc
import logging
from typing import Dict, Any, List

logger = logging.getLogger("stability_monitor")

class StabilityMonitor:
    """Tracks memory, tasks, and system resource degradation."""

    def __init__(self):
        self.baseline_memory = 0
        self.baseline_tasks = 0
        self.snapshots = []
        self._running = False
        self.saved_handlers = []

    def start_baseline(self):
        # Temporarily detach root log handlers to prevent pytest memory leaks from log accumulation
        self.saved_handlers = logging.root.handlers[:]
        logging.root.handlers = []
        
        # Save previous disable level and globally disable logging below CRITICAL
        self.saved_logging_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        
        tracemalloc.start()
        # Force garbage collection to get an accurate baseline
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        self.baseline_memory = current
        
        # Get baseline active tasks (excluding the monitor itself if it was a task)
        try:
            loop = asyncio.get_running_loop()
            self.baseline_tasks = len(asyncio.all_tasks(loop))
        except RuntimeError:
            self.baseline_tasks = 0
            
        logger.info(f"Stability Monitor Baseline: {self.baseline_memory / 1024:.2f} KB, {self.baseline_tasks} Tasks.")

    def take_snapshot(self, iteration: int) -> Dict[str, Any]:
        """Takes a snapshot of system resources at the given iteration."""
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        
        try:
            loop = asyncio.get_running_loop()
            active_tasks = len(asyncio.all_tasks(loop))
        except RuntimeError:
            active_tasks = 0
            
        mem_growth = current - self.baseline_memory
        snapshot_alloc = tracemalloc.take_snapshot()
        top_stats = snapshot_alloc.statistics("lineno")
        print("--- TOP 10 ALLOCATIONS ---")
        for index, stat in enumerate(top_stats[:10], 1):
            print(f"#{index}: {stat}")
        print("--------------------------")
        task_growth = active_tasks - self.baseline_tasks
        
        snapshot = {
            "iteration": iteration,
            "memory_current_kb": current / 1024,
            "memory_peak_kb": peak / 1024,
            "memory_growth_kb": mem_growth / 1024,
            "active_tasks": active_tasks,
            "task_growth": task_growth,
            "gc_objects": len(gc.get_objects())
        }
        self.snapshots.append(snapshot)
        return snapshot

    def stop(self):
        tracemalloc.stop()
        # Restore logging disable level
        if hasattr(self, "saved_logging_disable"):
            logging.disable(self.saved_logging_disable)
        # Restore root handlers
        if self.saved_handlers:
            logging.root.handlers = self.saved_handlers

    def detect_leaks(self, memory_threshold_kb=5000, task_threshold=5) -> List[str]:
        """Detects if degradation thresholds have been breached across snapshots."""
        warnings = []
        if not self.snapshots:
            return warnings
            
        latest = self.snapshots[-1]
        
        if latest["memory_growth_kb"] > memory_threshold_kb:
            warnings.append(f"Memory Leak Detected: Growth exceeded {memory_threshold_kb} KB limit (Currently {latest['memory_growth_kb']:.2f} KB)")
            
        if latest["task_growth"] > task_threshold:
            warnings.append(f"Task Leak Detected: Unreleased asyncio tasks exceeded {task_threshold} limit (Currently {latest['task_growth']})")
            
        return warnings
