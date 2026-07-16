import pytest
import asyncio
from unittest.mock import MagicMock

from runtimes.direct import DirectRuntime
from runtimes.base import RuntimeContract
from contracts.workflow import TaskControlBlock, CapabilityProfile

@pytest.fixture
def mock_router():
    router = MagicMock()
    # Return (provider, model, metadata) for resolve_capability
    router.resolve_capability.return_value = ("low_provider", "low_model", {})
    return router

@pytest.mark.asyncio
async def test_direct_runtime_imports_and_contract(mock_router):
    runtime = DirectRuntime(router=mock_router)
    assert isinstance(runtime, RuntimeContract)

@pytest.mark.asyncio
async def test_direct_runtime_execution(mock_router, monkeypatch):
    # We patch httpx.AsyncClient.post to return a mocked response
    class MockResponse:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "Direct Mocked HTTP Response"}}]}

    async def mock_post(*args, **kwargs):
        return MockResponse()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    # Give a dummy API key so it doesn't short circuit to the test stub
    monkeypatch.setenv("OPENROUTER_API_KEY", "real-key")

    runtime = DirectRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="DIRECT",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"prompt": "Hello"})
    
    result = await runtime.execute()
    
    # Assert CapabilityProfile minimum reasoning tier is LOW
    call_args = mock_router.resolve_capability.call_args[0][0]
    assert call_args.minimum_reasoning_tier == "LOW"
    
    assert result.output == "Direct Mocked HTTP Response"
    assert result.winner == "low_provider/low_model"
    assert result.provider == "low_provider"
    assert result.model == "low_model"
    assert "prompt_tokens" in result.token_usage
    assert result.estimated_cost_usd > 0
    assert result.latency_ms > 0
    assert result.runtime_type == "DIRECT"

@pytest.mark.asyncio
async def test_direct_runtime_timeout_enforcement(mock_router, monkeypatch):
    async def mock_post_timeout(*args, **kwargs):
        await asyncio.sleep(10.0) # sleep beyond timeout
    
    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_timeout)
    monkeypatch.setenv("OPENROUTER_API_KEY", "real-key")

    runtime = DirectRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="DIRECT",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    # Inject simulation flag to shorten timeout to 0.05s
    await runtime.initialize({"prompt": "Hello", "_sim_direct_timeout": True})
    
    result = await runtime.execute()
    
    assert result.output == "FAILED: Timeout"
    assert result.reason == "Timeout"
    assert result.winner == "None"
