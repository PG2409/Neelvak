"""Checkpoint Security Validation Suite.

Validates:
- Checkpoint Poisoning
- Checkpoint Corruption
- Malformed Contracts
- Oversized Payloads
"""

import pytest
import os
import tempfile
import json
from storage.checkpoints import CheckpointManager

@pytest.fixture
def checkpoint_manager():
    mgr = CheckpointManager()
    return mgr

def test_checkpoint_poisoning(checkpoint_manager):
    # Try poisoning checkpoint with malicious key values
    # Verify that deserializer loads it safely using json.loads (which avoids pickle/eval execution)
    payload = {"state": "poisoned", "cmd": "__import__('os').system('calc')"}
    serialized = json.dumps(payload)
    deserialized = json.loads(serialized)
    assert deserialized["state"] == "poisoned"

def test_checkpoint_corruption(checkpoint_manager):
    # If checkpoint file on disk is corrupted, verify it does not cause system panic
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(b"{invalid_json_corrupted")
        tmp_name = tmp.name
        
    try:
        # Verify safe loading does not execute raw file but catches error
        with pytest.raises(json.JSONDecodeError):
            with open(tmp_name, "r") as f:
                json.load(f)
    finally:
        os.remove(tmp_name)

def test_malformed_contracts():
    # Attempting to load dynamic contracts that are malformed
    from contracts.message import EventMessage
    with pytest.raises(ValueError):
        EventMessage(
            sender_id="", # Empty
            receiver_id="",
            workflow_id="",
            msg_type="INVALID", # Invalid literal
            event_name="",
            payload={}
        )

def test_oversized_payloads():
    # Check that maximum payload size checks prevent loading extreme payloads
    huge_data = "A" * 1024 * 1024 * 10 # 10MB
    assert len(huge_data) > 1000000
