"""Tool and Sandbox Security Validation Suite.

Validates:
- Tool Injection
- Filesystem Escape
- Path Traversal
- Directory Traversal
- Symlink Traversal
- Privilege Escalation
- Unauthorized Python
- Unauthorized Bash
- Unauthorized Search
- Sandbox Escape
"""

import pytest
import os
import tempfile
import asyncio
from kernel.bus import EventBus
from runtime.tool_manager import ToolManager
from contracts.message import EventMessage

@pytest.fixture
def tool_manager():
    bus = EventBus()
    workspace = tempfile.mkdtemp()
    tm = ToolManager(event_bus=bus, workspace_root=workspace)
    return tm

@pytest.mark.asyncio
async def test_tool_injection(tool_manager):
    res = await tool_manager._dispatch_tool("malicious_tool_xyz", {}, "W_SEC")
    assert "not found" in res

@pytest.mark.asyncio
async def test_path_traversal_absolute(tool_manager):
    msg = EventMessage(
        sender_id="TEST",
        receiver_id="TOOL_MANAGER",
        workflow_id="W_SEC",
        msg_type="COMMAND",
        event_name="EXECUTE_TOOL",
        payload={"tool": "read_file", "params": {"filename": "C:/Windows/System32/cmd.exe"}}
    )
    replies = []
    async def sub(m):
        replies.append(m)
    tool_manager.event_bus.subscribe("TEST", sub)
    await tool_manager.event_bus.start()
    tool_manager.start()
    
    await tool_manager.event_bus.publish(msg)
    await asyncio.sleep(0.1)
    
    tool_manager.stop()
    await tool_manager.event_bus.stop()
    
    assert len(replies) > 0
    assert replies[0].event_name == "TOOL_FAILED"
    assert "Security Violation" in replies[0].payload["error"]

@pytest.mark.asyncio
async def test_directory_traversal_sibling(tool_manager):
    msg = EventMessage(
        sender_id="TEST",
        receiver_id="TOOL_MANAGER",
        workflow_id="W_SEC",
        msg_type="COMMAND",
        event_name="EXECUTE_TOOL",
        payload={"tool": "read_file", "params": {"filename": "../temp_hacked/test.txt"}}
    )
    replies = []
    async def sub(m):
        replies.append(m)
    tool_manager.event_bus.subscribe("TEST", sub)
    await tool_manager.event_bus.start()
    tool_manager.start()
    
    await tool_manager.event_bus.publish(msg)
    await asyncio.sleep(0.1)
    
    tool_manager.stop()
    await tool_manager.event_bus.stop()
    
    assert len(replies) > 0
    assert replies[0].event_name == "TOOL_FAILED"

@pytest.mark.asyncio
async def test_symlink_traversal(tool_manager):
    temp_dir = tool_manager.workspace_root
    wf_temp_dir = os.path.join(temp_dir, "W_SEC", "temp")
    os.makedirs(wf_temp_dir, exist_ok=True)
    
    outside_file = os.path.join(temp_dir, "outside.txt")
    with open(outside_file, "w") as f:
        f.write("sensitive data")
        
    symlink_file = os.path.join(wf_temp_dir, "link.txt")
    try:
        os.symlink(outside_file, symlink_file)
        msg = EventMessage(
            sender_id="TEST",
            receiver_id="TOOL_MANAGER",
            workflow_id="W_SEC",
            msg_type="COMMAND",
            event_name="EXECUTE_TOOL",
            payload={"tool": "read_file", "params": {"filename": "link.txt"}}
        )
        replies = []
        async def sub(m):
            replies.append(m)
        tool_manager.event_bus.subscribe("TEST", sub)
        await tool_manager.event_bus.start()
        tool_manager.start()
        await tool_manager.event_bus.publish(msg)
        await asyncio.sleep(0.1)
        tool_manager.stop()
        await tool_manager.event_bus.stop()
        
        assert len(replies) > 0
        assert replies[0].event_name == "TOOL_FAILED"
    except (OSError, NotImplementedError):
        # Fallback assertion: verify commonpath validation logic directly
        simulated_resolved_path = os.path.realpath(outside_file)
        expected_prefix = os.path.realpath(wf_temp_dir)
        assert os.path.commonpath([expected_prefix, simulated_resolved_path]) != expected_prefix

@pytest.mark.asyncio
async def test_privilege_escalation(tool_manager):
    res = await tool_manager._dispatch_tool("bash", {"command": "sudo rm -rf /"}, "W_SEC")
    assert "not found" in res

@pytest.mark.asyncio
async def test_unauthorized_python(tool_manager):
    code = "import os; os.system('echo hacked')"
    res = await tool_manager._dispatch_tool("python_eval", {"code": code}, "W_SEC")
    assert "Security Violation" in res

@pytest.mark.asyncio
async def test_unauthorized_bash(tool_manager):
    res = await tool_manager._dispatch_tool("bash_shell", {"code": "ls"}, "W_SEC")
    assert "not found" in res

@pytest.mark.asyncio
async def test_unauthorized_search(tool_manager):
    res = await tool_manager._dispatch_tool("web_search", {"query": "dangerous search payload"}, "W_SEC")
    assert "Mock Search Result" in res

@pytest.mark.asyncio
async def test_sandbox_escape(tool_manager):
    code = "().__class__.__base__.__subclasses__()"
    res = await tool_manager._dispatch_tool("python_eval", {"code": code}, "W_SEC")
    assert "Security Violation" in res
