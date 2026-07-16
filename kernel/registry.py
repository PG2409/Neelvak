"""Active Process Table (Distributed Ready).

Provides thread-safe registration and metadata checks for Process Control Blocks.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("neelvak_kernel")

class AgentRegistry:
    """Thread-safe Process Control Block directory utilizing asyncio lock rings."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._processes: Dict[str, Dict[str, Any]] = {}

    async def register(self, pcb_id: str, metadata: Dict[str, Any]) -> None:
        """Registers a new process mapping or updates metadata parameters.

        Args:
            pcb_id: Unique process ID string.
            metadata: Associated process parameters and state settings.
        """
        async with self._lock:
            self._processes[pcb_id] = {
                "agent_id": pcb_id,
                "role": metadata.get("role", "N/A"),
                "runtime": metadata.get("runtime", "STANDARD"),
                "workflow_node": metadata.get("workflow_node", "N/A"),
                "provider": metadata.get("provider", "N/A"),
                "model": metadata.get("model", "N/A"),
                "current_task": metadata.get("current_task", "N/A"),
                "status": metadata.get("status", "SPAWNED"),
                "retries": metadata.get("retries", 0),
                "execution_time_ms": metadata.get("execution_time_ms", 0.0),
                "current_state": metadata.get("current_state", "QUEUED"),
                # Legacy fields for backward compatibility
                "parent_id": metadata.get("parent_id"),
                "child_ids": metadata.get("child_ids", []),
                "state": metadata.get("state", "SPAWNED"),
                "created_at": metadata.get("created_at", asyncio.get_event_loop().time())
            }
            logger.info(f"Registered process {pcb_id} in registry.")

    async def update_state(self, pcb_id: str, state: str) -> None:
        """Modifies a process state setting.

        Args:
            pcb_id: Unique process ID.
            state: New state label.
        """
        async with self._lock:
            if pcb_id in self._processes:
                self._processes[pcb_id]["current_state"] = state
                self._processes[pcb_id]["state"] = state
                logger.info(f"Updated process {pcb_id} state to {state}.")

    async def add_child(self, parent_id: str, child_id: str) -> None:
        """Links a child process to a parent process.

        Args:
            parent_id: Parent process ID.
            child_id: Child process ID.
        """
        async with self._lock:
            if parent_id in self._processes:
                self._processes[parent_id]["child_ids"].append(child_id)

    async def get(self, pcb_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves registered details for a specific PCB.

        Args:
            pcb_id: Process identifier.

        Returns:
            The metadata dictionary or None.
        """
        async with self._lock:
            return self._processes.get(pcb_id)

    async def get_all(self) -> List[Dict[str, Any]]:
        """Returns copies of all active records in the process table."""
        async with self._lock:
            return list(self._processes.values())

    async def remove(self, pcb_id: str) -> None:
        """Removes a process record from the process table.

        Args:
            pcb_id: Process identifier.
        """
        async with self._lock:
            if pcb_id in self._processes:
                del self._processes[pcb_id]
                logger.info(f"Removed process {pcb_id} from registry.")
