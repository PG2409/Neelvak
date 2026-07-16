import pytest
from tests.behavioral.engine import BehavioralEngine

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.mark.asyncio
async def test_direct_success(engine):
    result, logs = await engine.execute_simulated_runtime("DIRECT", {})
    assert "Direct Mock Result" in result.output
    assert result.winner is not None

@pytest.mark.asyncio
async def test_direct_timeout(engine):
    result, logs = await engine.execute_simulated_runtime("DIRECT", {"_sim_direct_timeout": True})
    assert result.output == "FAILED: Timeout"
    assert result.reason == "Timeout"

@pytest.mark.asyncio
async def test_direct_fail(engine):
    with pytest.raises(RuntimeError, match="Simulated failure"):
        await engine.execute_simulated_runtime("DIRECT", {"_sim_direct_fail": True})
