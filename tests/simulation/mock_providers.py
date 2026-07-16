"""Simulation Mocks for Provider Latency and Fault Injection.

This module provides an HTTP client mock or async interceptor that replicates
the behavior of unreliable remote LLM providers (Groq/OpenRouter).
"""

import asyncio
import json
import logging
import random
from typing import Any, Dict

logger = logging.getLogger("neelvak_kernel")

class MockProviderEndpoint:
    """A synthetic endpoint that mimics intermittent failures, rate limits, and latency."""

    def __init__(self, failure_rate: float = 0.0, latency_range: tuple = (0.1, 0.5), force_429_rate: float = 0.0):
        self.failure_rate = failure_rate
        self.latency_range = latency_range
        self.force_429_rate = force_429_rate
        
        self.total_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0

    async def call_completion(self, provider: str, model: str, prompt: str) -> str:
        """Simulate an HTTP request to the provider."""
        self.total_requests += 1
        
        # Simulate Network Latency
        latency = random.uniform(*self.latency_range)
        await asyncio.sleep(latency)
        
        # Simulate 429 Rate Limit Throttling
        if random.random() < self.force_429_rate:
            self.rate_limited_requests += 1
            logger.warning(f"MockProvider: Simulated HTTP 429 Too Many Requests from {provider}")
            raise RuntimeError(f"HTTP Endpoint error 429: Too Many Requests from {provider}")
            
        # Simulate 500 Internal Server Error
        if random.random() < self.failure_rate:
            self.failed_requests += 1
            logger.warning(f"MockProvider: Simulated HTTP 500 Internal Server Error from {provider}")
            raise RuntimeError(f"HTTP Endpoint error 500: Internal Server Error from {provider}")
            
        # Simulated successful return
        return json.dumps({
            "status": "success", 
            "result": f"Simulated output from {model} on {provider} for prompt: {prompt[:20]}..."
        })

# Global mock instance for testing
global_mock_endpoint = MockProviderEndpoint()
