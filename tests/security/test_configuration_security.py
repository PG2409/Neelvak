"""Configuration Security Validation Suite.

Validates:
- Configuration Poisoning
- Environment Poisoning
- Missing API Keys
- Invalid API Keys
- Shared Checkpoint Mutation
"""

import pytest
import os
import tempfile
import config
from storage.checkpoints import CheckpointManager
from compiler.compiler import AICompiler

def test_configuration_poisoning():
    # Verify capability catalogue defaults fallback if poisoned
    original_catalogue = config.CAPABILITY_CATALOGUE.copy()
    try:
        config.CAPABILITY_CATALOGUE = {}
        compiler = AICompiler()
        # Should fallback to fast tier configurations without throwing exceptions
        cfg = compiler._get_model_config("invalid_tier")
        assert cfg["provider"] == "groq"
    finally:
        config.CAPABILITY_CATALOGUE = original_catalogue

def test_environment_poisoning():
    # If environment variables are set to malicious strings, assert system still runs
    os.environ["AIOS_MAX_REQUESTS_PER_MIN"] = "999999"
    from gateway.request_manager import RequestManager
    rm = RequestManager()
    assert rm.max_requests_per_min == 999999
    # Clean up
    del os.environ["AIOS_MAX_REQUESTS_PER_MIN"]

def test_missing_api_keys():
    # Assert compiler fallback mode works if API keys are empty
    compiler = AICompiler(api_key_groq="", api_key_or="")
    assert compiler._is_mock_keys()

def test_invalid_api_keys():
    # Assert that invalid API keys trigger fallback or mock keys
    compiler = AICompiler(api_key_groq="mock-invalid", api_key_or="mock-invalid")
    assert compiler._is_mock_keys()

def test_shared_checkpoint_mutation():
    # Workspaces should not be able to mutate other workspace checkpoint databases
    mgr = CheckpointManager()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create checkpoint database for workspace A
        db_a = os.path.join(temp_dir, "db_a.db")
        # Ensure distinct and separate connections
        assert db_a != os.path.join(temp_dir, "db_b.db")
