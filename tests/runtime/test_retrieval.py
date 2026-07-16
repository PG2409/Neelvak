import pytest
import asyncio
from unittest.mock import MagicMock

from runtimes.retrieval import RetrievalRuntime
from runtimes.base import RuntimeContract
from contracts.workflow import TaskControlBlock, CapabilityProfile
from memory.manager import MemoryManager

@pytest.fixture
def memory_manager():
    # Use real MemoryManager to test internal promotion logic
    return MemoryManager(cache_dir="workspace/test_cache_retrieval")

@pytest.mark.asyncio
async def test_retrieval_runtime_imports_and_contract(memory_manager):
    runtime = RetrievalRuntime(memory_manager=memory_manager)
    assert isinstance(runtime, RuntimeContract)

@pytest.mark.asyncio
async def test_retrieval_zero_inference_hit(memory_manager):
    # Store something in L1 explicitly
    memory_manager._l1_cache["test_prompt"] = "Historical Data Payload"
    memory_manager._l1_stats["test_prompt"] = 0
    
    runtime = RetrievalRuntime(memory_manager=memory_manager)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="RETRIEVAL",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"prompt": "test_prompt"})
    
    result = await runtime.execute()
    
    assert result.output == "Historical Data Payload"
    assert result.winner == "Local Cache Index"
    assert result.confidence == 1.0
    assert result.reason == "Zero-Reasoning Local Cache HIT"
    assert result.token_usage == {"prompt_tokens": 0, "completion_tokens": 0}
    assert result.estimated_cost_usd == 0.0000
    assert result.latency_ms >= 0.0

@pytest.mark.asyncio
async def test_retrieval_cache_promotion_metrics(memory_manager):
    # Place something in L3
    memory_manager._l3_index["promotion_test"] = "Data to promote"
    memory_manager._l3_stats["promotion_test"] = 0
    
    runtime = RetrievalRuntime(memory_manager=memory_manager)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="RETRIEVAL",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    
    # Executing 3 times should hit the promotion threshold in MemoryManager
    for _ in range(3):
        await runtime.initialize({"prompt": "promotion_test"})
        await runtime.execute()
        
    # Verify promotion logic was triggered by checking L1 cache
    assert "promotion_test" in memory_manager._l1_cache
    assert memory_manager._l1_cache["promotion_test"] == "Data to promote"
    assert memory_manager._l1_stats["promotion_test"] >= 1

@pytest.mark.asyncio
async def test_retrieval_cache_miss(memory_manager):
    runtime = RetrievalRuntime(memory_manager=memory_manager)
    tcb = TaskControlBlock(
        workflow_id="test_wf",
        assigned_runtime="RETRIEVAL",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    await runtime.validate(tcb)
    await runtime.initialize({"prompt": "unknown_prompt"})
    
    result = await runtime.execute()
    
    assert result.winner == "Retrieval Fallback"
    assert result.confidence == 0.0
    assert "Cache miss" in result.reason
    assert result.token_usage == {"prompt_tokens": 0, "completion_tokens": 0}
    assert result.estimated_cost_usd == 0.0
