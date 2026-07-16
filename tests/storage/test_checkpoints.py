import pytest
import os
import json
import asyncio
from storage.adapter import JSONStorageAdapter
from storage.checkpoints import CheckpointManager

@pytest.fixture
def checkpoint_manager(tmp_path):
    adapter = JSONStorageAdapter(storage_dir=str(tmp_path))
    return CheckpointManager(adapter=adapter)

@pytest.mark.asyncio
async def test_checkpoint_save_and_load(checkpoint_manager):
    key = await checkpoint_manager.create_checkpoint(
        tcb_id="tcb_123",
        workflow_id="wf_1",
        state="RUNNING",
        context={"x": 1},
        log_trace=["Init"]
    )
    
    loaded = await checkpoint_manager.load_and_validate_checkpoint(key)
    assert loaded is not None
    assert loaded["tcb_id"] == "tcb_123"

@pytest.mark.asyncio
async def test_checkpoint_rejection_missing(checkpoint_manager):
    loaded = await checkpoint_manager.load_and_validate_checkpoint("non_existent")
    assert loaded is None

@pytest.mark.asyncio
async def test_checkpoint_rejection_corrupted(checkpoint_manager):
    # Manually create a corrupt checkpoint
    adapter = checkpoint_manager.adapter
    path = adapter._get_path("corrupt_cp")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ invalid json")
        
    loaded = await checkpoint_manager.load_and_validate_checkpoint("corrupt_cp")
    assert loaded is None

@pytest.mark.asyncio
async def test_checkpoint_rejection_schema_violation(checkpoint_manager):
    # Valid JSON but missing required schema fields
    adapter = checkpoint_manager.adapter
    path = adapter._get_path("schema_violator")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"random": "data"}, f)
        
    with pytest.raises(ValueError, match="Checkpoint file validation failed"):
        await checkpoint_manager.load_and_validate_checkpoint("schema_violator")

@pytest.mark.asyncio
async def test_execute_recovery_escalation_sequence(checkpoint_manager):
    # 1. Local Re-try
    res = await checkpoint_manager.execute_recovery_escalation("tcb_1", "wf_1", "API_TIMEOUT", {"retry_count": 0})
    assert res == "RETRY"
    
    # 2. Hot-Swap
    res = await checkpoint_manager.execute_recovery_escalation("tcb_1", "wf_1", "API_TIMEOUT", {"retry_count": 2, "hot_swap_attempted": False})
    assert res == "HOT_SWAP"
    
    # 3/4. Rollback and Resume (if checkpoint exists)
    await checkpoint_manager.create_checkpoint("tcb_1", "wf_1", "RUNNING", {}, [])
    res = await checkpoint_manager.execute_recovery_escalation("tcb_1", "wf_1", "API_TIMEOUT", {"retry_count": 2, "hot_swap_attempted": True})
    assert res == "RESUME"
    
    # 5/6. Terminate (if checkpoint missing or corrupted)
    await checkpoint_manager.adapter.delete("checkpoint_wf_1_tcb_1")
    res = await checkpoint_manager.execute_recovery_escalation("tcb_1", "wf_1", "API_TIMEOUT", {"retry_count": 2, "hot_swap_attempted": True})
    assert res == "TERMINATE"
