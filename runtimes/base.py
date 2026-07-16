"""Unified Runtime Contract Interface.

Abstract class defining methods exposed by all operational execution runtimes.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from contracts.workflow import TaskControlBlock, RuntimeResult

class RuntimeContract(ABC):
    """The absolute standard interface for all AIOS Execution Kernels."""

    @abstractmethod
    async def validate(self, tcb: TaskControlBlock) -> bool:
        """Verify task capabilities match kernel execution boundaries.

        Args:
            tcb: Task Control Block containing configuration requirements.

        Returns:
            True if task is supported by the runtime, False otherwise.
        """
        pass

    @abstractmethod
    async def initialize(self, env_context: Dict[str, Any]) -> None:
        """Allocate private workspace environment properties.

        Args:
            env_context: Sandbox configuration parameters.
        """
        pass

    @abstractmethod
    async def execute(self) -> RuntimeResult:
        """Run the core compute or retrieval loop and return a standardized result.

        Returns:
            Standardized RuntimeResult envelope containing output metrics.
        """
        pass

    @abstractmethod
    async def pause(self) -> bool:
        """Freeze execution frames safely.

        Returns:
            True if execution paused successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def resume(self) -> bool:
        """Thaw and reconstruct execution frames from active memory checkpoints.

        Returns:
            True if execution resumed successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def checkpoint(self) -> str:
        """Serialize localized runtime parameters to storage.

        Returns:
            Checkpoint reference ID.
        """
        pass

    @abstractmethod
    async def rollback(self, checkpoint_id: str) -> bool:
        """Revert local state contexts back to a verified baseline target.

        Args:
            checkpoint_id: Identifer key of the target checkpoint state.

        Returns:
            True if state rolled back successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Force process stop routines safely."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Release temporary directories, system caches, and active connections."""
        pass
