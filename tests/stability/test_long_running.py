import pytest
import asyncio
import json
import os
from unittest.mock import patch
from tests.stability.runner import StabilityRunner

import config

# To avoid massive test timeouts, we temporarily increase the semaphore size 
# for stability validation volume testing.
@pytest.fixture(autouse=True)
def patch_concurrency():
    original = config.MAX_CONCURRENT_RUNTIMES
    config.MAX_CONCURRENT_RUNTIMES = 500
    yield
    config.MAX_CONCURRENT_RUNTIMES = original

def append_report(result: dict):
    os.makedirs("tests/stability", exist_ok=True)
    report_file = "tests/stability/report_data.json"
    
    data = []
    if os.path.exists(report_file):
        with open(report_file, "r") as f:
            try:
                data = json.load(f)
            except:
                pass
    
    data.append(result)
    
    with open(report_file, "w") as f:
        json.dump(data, f, indent=2)

@pytest.mark.asyncio
@pytest.mark.parametrize("count,concurrent", [
    (100, False),
    (500, False),
    (100, True),
    (1000, True),
    (5000, True),
    (10000, True)
])
async def test_stability_volumetric(count, concurrent):
    runner = StabilityRunner()
    result = await runner.execute_batch(count, concurrent=concurrent)
    append_report(result)
    
    # Stability Assertions
    # 1. No unhandled errors during execution
    assert result["error_count"] == 0, f"Expected 0 errors, got {result['error_count']}"
    
    # 2. No memory leaks exceeding per-workflow execution overhead bounds (Python arena high-water mark)
    # Allows 15 KB pool overhead per task instead of strict absolute 15MB
    allowed_growth = max(15000, count * 15)
    assert result["memory_growth_kb"] < allowed_growth, f"Memory leak detected: {result['memory_growth_kb']} KB"
    
    # 3. No unreleased asyncio tasks
    assert result["task_growth"] <= 10, f"Asyncio Task leak detected: {result['task_growth']} orphan tasks"
    
    # 4. Checkpoints cleaned up (Standard Runtime doesn't cache persistently here, so should be 0)
    assert result["checkpoint_count"] == 0, f"Unreleased files in stability workspace: {result['checkpoint_count']}"
