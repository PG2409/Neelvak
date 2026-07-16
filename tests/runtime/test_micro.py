import pytest
import asyncio
from unittest.mock import MagicMock

from runtimes.micro import MicroRuntime
from runtimes.base import RuntimeContract
from contracts.workflow import TaskControlBlock, CapabilityProfile

@pytest.fixture
def mock_router():
    router = MagicMock()
    # Return (provider, model, metadata) for resolve_capability
    router.resolve_capability.return_value = ("low_provider", "low_model", {})
    return router

@pytest.mark.asyncio
async def test_micro_runtime_imports_and_contract(mock_router):
    runtime = MicroRuntime(router=mock_router)
    assert isinstance(runtime, RuntimeContract)
    assert runtime is not None

@pytest.mark.asyncio
async def test_micro_split_merge_concurrency_limit(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    # Pass 10 items, but concurrency limit is 5
    await runtime.initialize({"items": ["i1", "i2", "i3", "i4", "i5", "i6", "i7", "i8", "i9", "i10"]})
    
    result = await runtime.execute()
    
    assert mock_router.resolve_capability.call_count == 1
    assert result.winner == "Micro-Threader Pool"
    assert result.metrics["total_slices"] == 5
    assert result.metrics["failed_slices"] == 0
    assert "Item 1" in result.output
    assert "Resolved i1" in result.output
    assert "Item 5" in result.output
    assert "Resolved i5" in result.output
    assert "Item 6" not in result.output  # Because it stops at 5
    assert result.provider == "low_provider"
    assert result.model == "low_model"
    assert "prompt_tokens" in result.token_usage
    assert result.estimated_cost_usd > 0
    assert result.latency_ms > 0

@pytest.mark.asyncio
async def test_micro_empty_payload(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"items": []})
    
    result = await runtime.execute()
    assert result.metrics["total_slices"] == 0
    assert result.metrics["failed_slices"] == 0
    assert result.output == "### Micro-Threader Execution Results"

@pytest.mark.asyncio
async def test_micro_single_item(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"items": ["single"]})
    
    result = await runtime.execute()
    assert result.metrics["total_slices"] == 1
    assert "Resolved single" in result.output

@pytest.mark.asyncio
async def test_micro_partial_failure(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    # One fails permanently due to exhaustion mock flag
    await runtime.initialize({"items": ["good1", "fail_item", "good2", "good3"], "_sim_micro_exhaust_retries": True})
    
    result = await runtime.execute()
    
    assert result.metrics["total_slices"] == 4
    assert result.metrics["failed_slices"] == 1
    assert "Resolved good1" in result.output
    assert "Resolved good2" in result.output
    assert "Resolved good3" in result.output
    assert "fail_item" not in result.output
    assert "Success count: 3/4" in result.reason

@pytest.mark.asyncio
async def test_micro_complete_failure(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"items": ["fail1", "fail2", "fail3"], "_sim_micro_exhaust_retries": True})
    
    result = await runtime.execute()
    
    assert result.metrics["total_slices"] == 3
    assert result.metrics["failed_slices"] == 3
    assert "Success count: 0/3" in result.reason

@pytest.mark.asyncio
async def test_micro_timeout_enforcement(mock_router):
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"items": ["i1", "i2"], "_sim_micro_timeout": True})
    
    result = await runtime.execute()
    assert result.output == "FAILED: Timeout"
    assert result.reason == "Timeout"
    assert result.winner == "None"

@pytest.mark.asyncio
async def test_micro_worker_isolation_and_state(mock_router):
    # Verifies workers do not share mutable state inadvertently
    runtime = MicroRuntime(router=mock_router)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="MICRO",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"items": ["A", "B", "C"]})
    result = await runtime.execute()
    
    # Internal metrics lists results
    res_list = result.metrics["results"]
    assert len(res_list) == 3
    # Check they all succeeded uniquely
    assert all(r["status"] == "success" for r in res_list)
    assert res_list[0]["data"] == "Resolved A"
    assert res_list[1]["data"] == "Resolved B"
    assert res_list[2]["data"] == "Resolved C"
