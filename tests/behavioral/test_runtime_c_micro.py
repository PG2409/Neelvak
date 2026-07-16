import pytest
from tests.behavioral.engine import BehavioralEngine

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.mark.asyncio
async def test_micro_split_merge_success(engine):
    # Pass 5 items
    items = ["item1", "item2", "item3", "item4", "item5"]
    result, logs = await engine.execute_simulated_runtime("MICRO", {"items": items})
    
    assert result.winner == "Micro-Threader Pool"
    assert result.metrics["total_slices"] == 5
    assert result.metrics["failed_slices"] == 0
    assert "Resolved item1" in result.output

@pytest.mark.asyncio
async def test_micro_retry_success(engine):
    # Include 'fail' in one item to trigger transient failure, which succeeds on retry 3
    items = ["fail_item"]
    result, logs = await engine.execute_simulated_runtime("MICRO", {"items": items})
    
    log_text = "\n".join(logs)
    assert "Attempt 1 failed - Simulated transient provider error." in log_text
    assert "Attempt 2 failed - Simulated transient provider error." in log_text
    assert result.metrics["failed_slices"] == 0
    assert "Resolved fail_item" in result.output

@pytest.mark.asyncio
async def test_micro_retry_exhaustion(engine):
    # exhaust retries
    items = ["fail_item"]
    result, logs = await engine.execute_simulated_runtime("MICRO", {"items": items, "_sim_micro_exhaust_retries": True})
    
    assert result.metrics["failed_slices"] == 1
    assert "Resolved fail_item" not in result.output
    
@pytest.mark.asyncio
async def test_micro_timeout(engine):
    items = ["item1", "item2", "item3", "item4", "item5"]
    result, logs = await engine.execute_simulated_runtime("MICRO", {"items": items, "_sim_micro_timeout": True})
    assert result.output == "FAILED: Timeout"
    assert result.reason == "Timeout"
