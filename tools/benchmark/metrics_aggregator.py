"""Metrics Aggregator.

Collects and parses system metrics, such as CSS Cache hit rates,
EventBus sizes, and provider fallback percentages.
"""

import json
import os
import glob
from typing import Dict, Any, List

class MetricsAggregator:
    def __init__(self, workspace_root: str = "C:/neelvak"):
        self.workspace_root = workspace_root
        
    def collect_memory_metrics(self) -> Dict[str, Any]:
        """Reads the memory store to estimate cache size and utilization."""
        store_path = os.path.join(self.workspace_root, "data_store.json")
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                l1 = data.get("L1", {})
                return {
                    "l1_cache_size": len(l1),
                    "status": "healthy"
                }
        except Exception:
            return {"l1_cache_size": 0, "status": "empty_or_missing"}

    def collect_checkpoint_metrics(self) -> Dict[str, Any]:
        """Counts active checkpoints to detect leaks or crashes."""
        checkpoint_dir = os.path.join(self.workspace_root, "data_store")
        if not os.path.exists(checkpoint_dir):
            return {"active_checkpoints": 0}
            
        files = glob.glob(os.path.join(checkpoint_dir, "checkpoint_*.json"))
        return {"active_checkpoints": len(files)}

    def generate_report(self, load_test_report: Dict[str, Any] = None) -> str:
        """Combines all metrics into a markdown report."""
        mem = self.collect_memory_metrics()
        chk = self.collect_checkpoint_metrics()
        
        report = []
        report.append("# AIOS Performance & Metrics Report\n")
        
        if load_test_report:
            report.append("## Load Test Results")
            report.append(f"- **Total Requests**: {load_test_report.get('total_requests', 0)}")
            report.append(f"- **Success Rate**: {load_test_report.get('successes', 0)} / {load_test_report.get('total_requests', 0)}")
            report.append(f"- **Throughput**: {load_test_report.get('throughput_req_per_s', 0):.2f} req/s")
            report.append(f"- **P50 Latency**: {load_test_report.get('latency_p50_s', 0):.3f}s")
            report.append(f"- **P95 Latency**: {load_test_report.get('latency_p95_s', 0):.3f}s\n")
            
        report.append("## System Metrics")
        report.append(f"- **L1 Cache Size**: {mem['l1_cache_size']} items")
        report.append(f"- **Active/Leaked Checkpoints**: {chk['active_checkpoints']} files")
        
        return "\n".join(report)

if __name__ == "__main__":
    agg = MetricsAggregator()
    print(agg.generate_report())
