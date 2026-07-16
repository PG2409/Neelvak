"""Stress Testing Metrics and Resource Tracker."""

import time
import tracemalloc
import json
import os
from typing import Dict, List, Any

class StressMetricsTracker:
    def __init__(self):
        self.latencies: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
        self.memory_snapshots: List[Dict[str, float]] = []
        self.bottlenecks: Dict[str, float] = {}

    def start_memory_tracking(self):
        """Starts tracemalloc to record memory pressure."""
        tracemalloc.start()

    def snapshot_memory(self, label: str):
        """Records current heap usage in MB."""
        if not tracemalloc.is_tracing():
            return
        current, peak = tracemalloc.get_traced_memory()
        self.memory_snapshots.append({
            "label": label,
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024
        })

    def stop_memory_tracking(self):
        if tracemalloc.is_tracing():
            tracemalloc.stop()

    def record_latency(self, metric_key: str, latency_sec: float):
        """Records latency for percentile analysis."""
        if metric_key not in self.latencies:
            self.latencies[metric_key] = []
        self.latencies[metric_key].append(latency_sec)

    def increment(self, counter_key: str, amount: int = 1):
        if counter_key not in self.counters:
            self.counters[counter_key] = 0
        self.counters[counter_key] += amount

    def record_bottleneck(self, subsystem: str, wait_time_sec: float):
        """Records blocking time for bottleneck ranking."""
        if subsystem not in self.bottlenecks:
            self.bottlenecks[subsystem] = 0.0
        self.bottlenecks[subsystem] += wait_time_sec

    def calculate_percentiles(self, metric_key: str) -> Dict[str, float]:
        lats = self.latencies.get(metric_key, [])
        if not lats:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "avg": 0.0, "count": 0}
        
        lats.sort()
        n = len(lats)
        return {
            "p50": lats[int(n * 0.50)],
            "p90": lats[int(n * 0.90)],
            "p95": lats[int(n * 0.95)],
            "p99": lats[int(n * 0.99)],
            "max": lats[-1],
            "avg": sum(lats) / n,
            "count": n
        }

    def dump_metrics(self, output_path: str):
        """Dumps metrics to JSON for the generator."""
        data = {
            "latencies": {},
            "counters": self.counters,
            "memory": self.memory_snapshots,
            "bottlenecks": self.bottlenecks
        }
        for k in self.latencies.keys():
            data["latencies"][k] = self.calculate_percentiles(k)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

# Global tracker for tests to import
tracker = StressMetricsTracker()
