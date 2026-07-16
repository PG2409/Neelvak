import os
import pytest
import asyncio
from typing import List
from contracts.message import EventMessage
from kernel.bus import EventBus
from runtime.tool_manager import ToolManager
from runtime.factory import EnvironmentFactory

class MockEventBus(EventBus):
    def __init__(self):
        super().__init__()
        self.published_messages: List[EventMessage] = []

    async def publish(self, message: EventMessage) -> None:
        self.published_messages.append(message)

@pytest.fixture
def mock_bus():
    return MockEventBus()

@pytest.fixture
def factory():
    return EnvironmentFactory(base_workspace="test_workspace")

@pytest.fixture
def tool_manager(mock_bus):
    manager = ToolManager(mock_bus, workspace_root="test_workspace")
    return manager

@pytest.mark.asyncio
async def test_directory_traversal_attack_block(tool_manager, mock_bus):
    """Verify that passing a target path with ../ results in immediate security denial."""
    workflow_id = "test-traversal-wf"
    
    # Construct malicious command
    command = EventMessage(
        sender_id="AGENT_1",
        receiver_id="TOOL_MANAGER",
        workflow_id=workflow_id,
        msg_type="COMMAND",
        event_name="EXECUTE_TOOL",
        payload={
            "tool": "write_file",
            "params": {
                "filename": "../../config.py",
                "content": "malicious code"
            },
            "tcb_id": "TCB_123"
        }
    )
    
    await tool_manager.handle_tool_call(command)
    
    # Check published messages for Audit log and Error response
    assert len(mock_bus.published_messages) == 2
    audit_msg = mock_bus.published_messages[0]
    response_msg = mock_bus.published_messages[1]
    
    assert audit_msg.event_name == "TOOL_AUDIT"
    assert audit_msg.payload["permission_status"] == "DENIED"
    assert "Path traversal detected" in audit_msg.payload["target_resource"] or "DENIED" in audit_msg.payload["permission_status"]
    
    assert response_msg.event_name == "TOOL_FAILED"
    assert "Path traversal detected" in response_msg.payload["error"]
    
    # Ensure file was not created
    malicious_path = os.path.abspath(os.path.join("test_workspace", workflow_id, "temp", "../../config.py"))
    assert not os.path.exists(malicious_path)

@pytest.mark.asyncio
async def test_path_scoping_verification(tool_manager, mock_bus, factory):
    """Assert successful file creation places artifact strictly within workspace/{workflow_id}/temp/"""
    workflow_id = "test-scoping-wf"
    factory.provision_container(workflow_id)
    
    filename = "safe_artifact.txt"
    command = EventMessage(
        sender_id="AGENT_1",
        receiver_id="TOOL_MANAGER",
        workflow_id=workflow_id,
        msg_type="COMMAND",
        event_name="EXECUTE_TOOL",
        payload={
            "tool": "write_file",
            "params": {
                "filename": filename,
                "content": "safe content"
            },
            "tcb_id": "TCB_123"
        }
    )
    
    await tool_manager.handle_tool_call(command)
    
    # Verify file location on disk
    expected_path = os.path.join("test_workspace", workflow_id, "temp", filename)
    assert os.path.exists(expected_path)
    
    with open(expected_path, "r", encoding="utf-8") as f:
        assert f.read() == "safe content"
        
    factory.deprovision_container(workflow_id)

def test_clean_purge_sweep(factory):
    """Verify deprovision_container leaves target workspace completely erased."""
    workflow_id = "test-purge-wf"
    factory.provision_container(workflow_id)
    
    # Write some dummy files in temp and cache
    cache_file = os.path.join("test_workspace", workflow_id, "cache", "dummy.cache")
    temp_file = os.path.join("test_workspace", workflow_id, "temp", "dummy.temp")
    
    with open(cache_file, "w") as f:
        f.write("cache")
    with open(temp_file, "w") as f:
        f.write("temp")
        
    assert os.path.exists(cache_file)
    assert os.path.exists(temp_file)
    
    # Deprovision
    factory.deprovision_container(workflow_id)
    
    # Verify entire folder is gone
    workspace_path = os.path.join("test_workspace", workflow_id)
    assert not os.path.exists(workspace_path)
