import pytest
import asyncio
from unittest.mock import MagicMock

from runtimes.standard import StandardRuntime
from contracts.workflow import TaskControlBlock, CapabilityProfile
from contracts.message import EventMessage
from kernel.bus import EventBus

@pytest.fixture
def mock_router():
    router = MagicMock()
    # Return (provider, model, metadata) for resolve_capability
    router.resolve_capability.side_effect = [
        ("primary_provider", "primary_model", {}),
        ("surveillance_provider", "surveillance_model", {})
    ]
    return router

@pytest.mark.asyncio
async def test_standard_runtime_imports_and_initializes(mock_router):
    bus = EventBus()
    runtime = StandardRuntime(router=mock_router, event_bus=bus)
    assert runtime is not None

@pytest.mark.asyncio
async def test_standard_runtime_execution_flow(mock_router):
    bus = EventBus()
    await bus.start()
    try:
        runtime = StandardRuntime(router=mock_router, event_bus=bus)
        tcb = TaskControlBlock(
            workflow_id="test_wf",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD")
        )
        await runtime.validate(tcb)
        await runtime.initialize({})
        
        result = await runtime.execute()
        
        # Verify exactly two provider requests issued (1 for worker, 1 for surveillance)
        assert mock_router.resolve_capability.call_count == 2
        calls = mock_router.resolve_capability.call_args_list
        assert calls[0][0][0].minimum_reasoning_tier == "STANDARD"
        assert calls[1][0][0].minimum_reasoning_tier == "LOW"
        
        assert result.winner == "Worker Agent"
        assert result.provider == "primary_provider"
        assert result.model == "primary_model"
        assert result.confidence == 0.8
        assert "prompt_tokens" in result.token_usage
        assert "completion_tokens" in result.token_usage
        assert result.estimated_cost_usd > 0
        assert result.latency_ms > 0
        assert "alerts" in result.metrics
        assert result.metrics["surveillance_provider"] == "surveillance_provider"
        assert result.metrics["surveillance_model"] == "surveillance_model"
    finally:
        await bus.stop()

@pytest.mark.asyncio
async def test_surveillance_detects_token_overflow(mock_router):
    bus = EventBus()
    await bus.start()
    try:
        runtime = StandardRuntime(router=mock_router, event_bus=bus)
        tcb = TaskControlBlock(
            workflow_id="test_wf",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD"),
            payload={"_sim_worker_overflow": True}
        )
        await runtime.validate(tcb)
        await runtime.initialize(tcb.payload)
        
        result = await runtime.execute()
        
        assert "alerts" in result.metrics
        alerts = result.metrics["alerts"]
        assert any("Token overflow detected" in a for a in alerts)
    finally:
        await bus.stop()

@pytest.mark.asyncio
async def test_surveillance_detects_refusal(mock_router):
    bus = EventBus()
    await bus.start()
    try:
        runtime = StandardRuntime(router=mock_router, event_bus=bus)
        tcb = TaskControlBlock(
            workflow_id="test_wf",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD"),
            payload={"_sim_worker_hallucinate": True}
        )
        await runtime.validate(tcb)
        await runtime.initialize(tcb.payload)
        
        result = await runtime.execute()
        
        assert "alerts" in result.metrics
        alerts = result.metrics["alerts"]
        assert any("Refusal phrase matching detected" in a for a in alerts)
    finally:
        await bus.stop()

@pytest.mark.asyncio
async def test_worker_cancellation(mock_router):
    bus = EventBus()
    await bus.start()
    try:
        runtime = StandardRuntime(router=mock_router, event_bus=bus)
        tcb = TaskControlBlock(
            workflow_id="test_wf",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD")
        )
        await runtime.validate(tcb)
        await runtime.initialize(tcb.payload)
        
        # We just ensure cleanup works smoothly
        await runtime.terminate()
        await runtime.cleanup()
        assert runtime._tcb is None
    finally:
        await bus.stop()
