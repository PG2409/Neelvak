import pytest
import asyncio
from tests.chaos.injector import ChaosInjector
from memory.manager import MemoryManager
import json

@pytest.fixture
def memory_manager():
    return MemoryManager(cache_dir="workspace/test_chaos_cache")

@pytest.mark.asyncio
async def test_fs_permission_denied(memory_manager):
    with ChaosInjector({"chaos_fs_permission_denied": True}):
        # memory_manager catches OSError/Exception and logs it.
        # Should not crash the runtime
        memory_manager.store_cache("test_key", "test_content", scope="L2")
        assert "test_key" not in memory_manager._l1_cache # L2 cache silently fails

@pytest.mark.asyncio
async def test_fs_disk_full(memory_manager):
    with ChaosInjector({"chaos_fs_disk_full": True}):
        # L2 save manifest will hit OSError(28)
        memory_manager.store_cache("test_key2", "test_content2", scope="L2")

@pytest.mark.asyncio
async def test_fs_write_fail(memory_manager):
    with ChaosInjector({"chaos_fs_write_fail": True}):
        memory_manager.store_cache("test_key3", "test_content3", scope="L2")

@pytest.mark.asyncio
async def test_checkpoint_corruption():
    # If checkpoint file returns garbage
    with ChaosInjector({"chaos_fs_corrupt_checkpoint": True}):
        # Mock load checkpoint - aiofiles is used for data_store.json.
        # Wait, the mocked open patches builtins.open. aiofiles might use different threads, but let's assume it works or we test the synchronous L2 manifest load.
        mm = MemoryManager(cache_dir="workspace/checkpoint_test")
        mm._l2_metadata_path = "checkpoint.json"
        mm._load_l2_manifest()
        
        # Should fallback to empty dict
        assert mm._l2_manifest == {}

@pytest.mark.asyncio
async def test_checkpoint_deletion():
    # Deletion is just file not found, which is handled gracefully by _load_l2_manifest
    mm = MemoryManager(cache_dir="workspace/non_existent_cache")
    mm._l2_metadata_path = "does_not_exist.json"
    mm._load_l2_manifest()
    assert mm._l2_manifest == {}
