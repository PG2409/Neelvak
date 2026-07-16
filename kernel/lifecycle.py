"""Process Lifecycle Transaction Engine.

Governs Process Control Block parameters and state transitions.
"""

import logging
from enum import Enum
from typing import Dict, Any, List

logger = logging.getLogger("neelvak_kernel")

class ProcessState(str, Enum):
    """Rigid state parameters for process lifecycle."""
    SPAWNED = "SPAWNED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    UNDER_REVIEW = "UNDER_REVIEW"
    TERMINATED = "TERMINATED"

class TerminationReason(str, Enum):
    """Standard identifiers explaining process termination."""
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    KILLED = "KILLED"
    FAILED_OVER = "FAILED_OVER"

class ProcessControlBlock:
    """Model tracking active parameters, log buffers, and transitions for an execution."""

    def __init__(self, pcb_id: str, workflow_id: str, runtime: str) -> None:
        self.pcb_id = pcb_id
        self.workflow_id = workflow_id
        self.runtime = runtime
        self._state: ProcessState = ProcessState.SPAWNED
        self._private_memory: List[str] = []
        self._context: Dict[str, Any] = {}
        self.termination_reason: Optional[TerminationReason] = None

    @property
    def state(self) -> ProcessState:
        """Returns current process state."""
        return self._state

    def append_log(self, log_entry: str) -> None:
        """Pushes a message into internal log window (capped at 50 logs)."""
        self._private_memory.append(log_entry)
        if len(self._private_memory) > 50:
            self._private_memory.pop(0)

    def get_logs(self) -> List[str]:
        """Returns the private log trace."""
        return list(self._private_memory)

    def update_context(self, key: str, value: Any) -> None:
        """Updates internal variable settings."""
        self._context[key] = value

    def get_context(self) -> Dict[str, Any]:
        """Returns current context map."""
        return dict(self._context)


class LifecycleManager:
    """Main state transition coordinator enforcing transaction safety checks."""

    # Explicit state transition allowance matrix
    VALID_TRANSITIONS = {
        ProcessState.SPAWNED: {ProcessState.QUEUED, ProcessState.TERMINATED},
        ProcessState.QUEUED: {ProcessState.EXECUTING, ProcessState.TERMINATED},
        ProcessState.EXECUTING: {ProcessState.UNDER_REVIEW, ProcessState.TERMINATED},
        ProcessState.UNDER_REVIEW: {ProcessState.TERMINATED},
        ProcessState.TERMINATED: set()  # Terminal state
    }

    def __init__(self) -> None:
        pass

    def transition(self, pcb: ProcessControlBlock, next_state: ProcessState, reason: Optional[TerminationReason] = None) -> bool:
        """Validates and executes a transition over a PCB.

        Args:
            pcb: The Process Control Block instance.
            next_state: The proposed target state.
            reason: Optional explanation if entering a terminated state.

        Returns:
            True if the state change occurred, False otherwise.
        """
        current = pcb.state
        allowed = self.VALID_TRANSITIONS.get(current, set())
        
        if next_state in allowed:
            pcb._state = next_state
            if next_state == ProcessState.TERMINATED and reason:
                pcb.termination_reason = reason
            
            logger.info(f"Transitioned PCB {pcb.pcb_id}: {current} -> {next_state}")
            return True
        else:
            logger.warning(f"Illegal lifecycle transition attempted for PCB {pcb.pcb_id}: {current} -> {next_state}")
            return False
