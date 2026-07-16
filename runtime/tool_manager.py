"""Secure Sandbox Tool Manager & Permissions Ring.

Validates permissions, runs virtual device calls, and writes security logs.
"""

import os
import sys
import logging
import asyncio
import time
from typing import Dict, Any, List
from contracts.message import EventMessage
from kernel.bus import EventBus

logger = logging.getLogger("neelvak_kernel")

class ToolManager:
    """Checks safety rings and executes sandboxed commands from EventBus commands."""

    def __init__(self, event_bus: EventBus, workspace_root: str = "workspace") -> None:
        self.event_bus = event_bus
        self.workspace_root = workspace_root
        
        # Permissions directory ring policy: allowed directories and commands
        self._allowed_tools = {"read_file", "write_file", "python_eval", "web_search"}

    def start(self) -> None:
        """Subscribes the ToolManager to EventBus tool command channels."""
        self.event_bus.subscribe("TOOL_MANAGER", self.handle_tool_call)
        logger.info("ToolManager listener attached to EventBus.")

    def stop(self) -> None:
        """Unsubscribes the ToolManager from EventBus tool command channels."""
        self.event_bus.unsubscribe("TOOL_MANAGER", self.handle_tool_call)
        logger.info("ToolManager listener detached from EventBus.")

    async def _publish_audit(self, workflow_id: str, tcb_id: str, tool: str, target_resource: str, allowed: bool, duration_ms: float) -> None:
        """Publishes an unalterable security trace event to the EventBus."""
        audit_payload = {
            "timestamp": time.time(),
            "tcb_id": tcb_id,
            "tool_name": tool,
            "target_resource": target_resource,
            "permission_status": "GRANTED" if allowed else "DENIED",
            "execution_duration_ms": duration_ms
        }
        
        audit_msg = EventMessage(
            sender_id="TOOL_MANAGER",
            receiver_id="SYSTEM_MONITOR",
            workflow_id=workflow_id,
            msg_type="EVENT",
            event_name="TOOL_AUDIT",
            payload=audit_payload
        )
        
        try:
            await self.event_bus.publish(audit_msg)
        except Exception as e:
            logger.error(f"Failed to publish tool security audit log: {e}")

    async def handle_tool_call(self, message: EventMessage) -> None:
        """Processes incoming tool execution command requests."""
        start_time = time.time()
        
        if message.msg_type != "COMMAND" or message.event_name != "EXECUTE_TOOL":
            return

        payload = message.payload
        tool_name = payload.get("tool")
        params = payload.get("params", {})
        tcb_id = payload.get("tcb_id", "UNKNOWN_TCB")
        workflow_id = message.workflow_id
        sender_id = message.sender_id
        
        target_resource = params.get("filename", "N/A") if tool_name in ["read_file", "write_file"] else str(tool_name)

        # 1. Evaluate permissions ring
        if tool_name not in self._allowed_tools:
            err_msg = f"Security Violation: Tool '{tool_name}' is not in the system permissions ring."
            logger.warning(err_msg)
            duration_ms = (time.time() - start_time) * 1000.0
            await self._publish_audit(workflow_id, tcb_id, str(tool_name), target_resource, False, duration_ms)
            await self._respond_error(message, sender_id, err_msg)
            return

        # 2. Enforce sandbox directory path check
        if tool_name in ["read_file", "write_file"]:
            filename = params.get("filename", "")
            
            # Absolute denial on directory traversal sequences
            if "../" in filename or "..\\" in filename:
                err_msg = f"Security Violation: Path traversal detected on path: '{filename}'"
                logger.warning(err_msg)
                duration_ms = (time.time() - start_time) * 1000.0
                await self._publish_audit(workflow_id, tcb_id, tool_name, target_resource, False, duration_ms)
                await self._respond_error(message, sender_id, err_msg)
                return

            # Ensure path matches workspace limits (specifically within /temp/)
            # Using realpath to resolve symbolic links and avoid symlink traversal attacks
            resolved_path = os.path.realpath(os.path.join(self.workspace_root, workflow_id, "temp", filename))
            expected_prefix = os.path.realpath(os.path.join(self.workspace_root, workflow_id, "temp"))
            
            is_valid = False
            try:
                if os.path.commonpath([expected_prefix, resolved_path]) == expected_prefix:
                    is_valid = True
            except ValueError:
                pass # Different drives on Windows
                
            if not is_valid:
                err_msg = f"Security Violation: Path bounded sandbox violation on path: '{filename}'"
                logger.warning(err_msg)
                duration_ms = (time.time() - start_time) * 1000.0
                await self._publish_audit(workflow_id, tcb_id, tool_name, target_resource, False, duration_ms)
                await self._respond_error(message, sender_id, err_msg)
                return

        # 3. Execute tool
        try:
            result = await self._dispatch_tool(tool_name, params, workflow_id)
            duration_ms = (time.time() - start_time) * 1000.0
            await self._publish_audit(workflow_id, tcb_id, tool_name, target_resource, True, duration_ms)
            await self._respond_success(message, sender_id, result)
        except Exception as e:
            err_msg = f"Execution Exception during tool execution: {e}"
            logger.error(err_msg)
            duration_ms = (time.time() - start_time) * 1000.0
            await self._publish_audit(workflow_id, tcb_id, tool_name, target_resource, True, duration_ms)
            await self._respond_error(message, sender_id, err_msg)

    async def _dispatch_tool(self, tool_name: str, params: Dict[str, Any], workflow_id: str) -> str:
        if tool_name == "read_file":
            filename = params.get("filename", "")
            filepath = os.path.join(self.workspace_root, workflow_id, "temp", filename)
            if not os.path.exists(filepath):
                return f"Error: file '{filename}' does not exist."
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
                
        elif tool_name == "write_file":
            filename = params.get("filename", "")
            content = params.get("content", "")
            filepath = os.path.join(self.workspace_root, workflow_id, "temp", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: written {len(content)} characters to '{filename}'."
            
        elif tool_name == "python_eval":
            # Evaluates inside a restricted namespace block
            code = params.get("code", "")
            
            if "import " in code or "import\t" in code or "__" in code or "eval(" in code or "exec(" in code:
                return "Security Violation: Imports and dunder methods are disabled in python_eval."
                
            # Remove dangerous builtins
            allowed_builtins = {
                "print": print, "range": range, "len": len, "int": int, "str": str, 
                "float": float, "bool": bool, "list": list, "dict": dict, "set": set, 
                "tuple": tuple, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
                "sum": sum, "min": min, "max": max, "abs": abs, "round": round
            }
            safe_globals = {"__builtins__": allowed_builtins}
            safe_locals = {}
            try:
                # Redirect standard stdout to capture print statements
                import io
                old_stdout = sys.stdout
                redirected = sys.stdout = io.StringIO()
                exec(code, safe_globals, safe_locals)
                sys.stdout = old_stdout
                output = redirected.getvalue()
                return f"Local output:\n{output}\nReturned local variables: {safe_locals}"
            except Exception as e:
                return f"Error evaluating code: {e}"
                
        elif tool_name == "web_search":
            query = params.get("query", "")
            # Return high-fidelity search result mock for local offline testing
            return f"Mock Search Result for '{query}': High-accuracy query matched in local repository indexes."

        return f"Tool '{tool_name}' not found."

    async def _respond_success(self, command_msg: EventMessage, receiver_id: str, output: str) -> None:
        response = EventMessage(
            sender_id="TOOL_MANAGER",
            receiver_id=receiver_id,
            workflow_id=command_msg.workflow_id,
            msg_type="EVENT",
            event_name="TOOL_EXECUTED",
            payload={"status": "success", "result": output}
        )
        await self.event_bus.publish(response)

    async def _respond_error(self, command_msg: EventMessage, receiver_id: str, error_details: str) -> None:
        response = EventMessage(
            sender_id="TOOL_MANAGER",
            receiver_id=receiver_id,
            workflow_id=command_msg.workflow_id,
            msg_type="EVENT",
            event_name="TOOL_FAILED",
            payload={"status": "error", "error": error_details}
        )
        await self.event_bus.publish(response)
