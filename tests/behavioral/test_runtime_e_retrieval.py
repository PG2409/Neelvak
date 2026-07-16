import pytest
from tests.behavioral.engine import BehavioralEngine

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.mark.asyncio
async def test_retrieval_cache_hit(engine):
    result, logs = await engine.execute_simulated_runtime("RETRIEVAL", {"_sim_retrieval_hit": True, "prompt": "test_query"})
    assert result.winner == "Local Cache Index"
    assert result.reason == "Zero-Reasoning Local Cache HIT"
    assert "Mocked cache content for test_query" in result.output

@pytest.mark.asyncio
async def test_retrieval_cache_miss(engine):
    result, logs = await engine.execute_simulated_runtime("RETRIEVAL", {"_sim_retrieval_hit": False, "prompt": "test_query"})
    assert result.winner == "Retrieval Fallback"
    assert "Cache miss." in result.reason
    assert "[Retrieval Fallback]" in result.output
