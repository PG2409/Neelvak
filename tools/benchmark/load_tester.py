"""Load Tester & Concurrency Benchmarking Utility.

Fires massive concurrent requests at the API Gateway to measure throughput
and validate semaphore throttling.
"""

import asyncio
import httpx
import time
import statistics
import logging
from typing import List, Dict, Any

logger = logging.getLogger("neelvak_benchmark")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

class LoadTester:
    """Submits rapid concurrent workloads."""

    def __init__(self, target_url: str = "http://127.0.0.1:8000/api/chat"):
        self.target_url = target_url
        self.latencies = []
        self.errors = 0
        self.successes = 0

    async def _send_request(self, client: httpx.AsyncClient, prompt: str) -> None:
        start_time = time.time()
        try:
            response = await client.post(self.target_url, json={"prompt": prompt}, timeout=30.0)
            latency = time.time() - start_time
            self.latencies.append(latency)
            
            if response.status_code == 200:
                self.successes += 1
            else:
                self.errors += 1
                logger.debug(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            self.errors += 1
            logger.debug(f"Request failed: {e}")

    async def run_load_test(self, total_requests: int = 100, concurrency: int = 20) -> Dict[str, Any]:
        """Runs the benchmark suite."""
        logger.info(f"Starting Load Test: {total_requests} requests at concurrency {concurrency}")
        
        self.latencies.clear()
        self.successes = 0
        self.errors = 0
        
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            # We'll batch requests by concurrency limits
            for i in range(0, total_requests, concurrency):
                batch_size = min(concurrency, total_requests - i)
                tasks = []
                for j in range(batch_size):
                    # Unique prompts to bypass cache unless we specifically want cache hits
                    prompt = f"Benchmarking system performance - query id {i+j}-{time.time()}"
                    tasks.append(asyncio.create_task(self._send_request(client, prompt)))
                
                await asyncio.gather(*tasks)

        total_time = time.time() - start_time
        
        p50 = statistics.median(self.latencies) if self.latencies else 0.0
        p95 = statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else max(self.latencies) if self.latencies else 0.0
        p99 = statistics.quantiles(self.latencies, n=100)[98] if len(self.latencies) >= 100 else max(self.latencies) if self.latencies else 0.0
        throughput = self.successes / total_time if total_time > 0 else 0.0
        
        report = {
            "total_requests": total_requests,
            "successes": self.successes,
            "errors": self.errors,
            "total_time_s": total_time,
            "throughput_req_per_s": throughput,
            "latency_p50_s": p50,
            "latency_p95_s": p95,
            "latency_p99_s": p99
        }
        
        logger.info("=== Load Test Results ===")
        logger.info(f"Successes: {self.successes}")
        logger.info(f"Errors: {self.errors}")
        logger.info(f"Throughput: {throughput:.2f} req/s")
        logger.info(f"P50 Latency: {p50:.3f}s")
        logger.info(f"P95 Latency: {p95:.3f}s")
        
        return report

if __name__ == "__main__":
    tester = LoadTester()
    asyncio.run(tester.run_load_test(total_requests=50, concurrency=10))
