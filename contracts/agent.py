"""Unified Agent Contract Interface.

Defines the lifecycle hooks implemented by all agent roles in the system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from contracts.message import EventMessage

class AgentContract(ABC):
    """Every system agent process thread must inherit from this uniform interface block."""
    
    @abstractmethod
    async def initialize(self, context_data: Dict[str, Any]) -> None:
        """Mount private context memories and map EventBus queue routing slots.

        Args:
            context_data: Initial state and execution context parameters.
        """
        pass

    @abstractmethod
    async def receive(self, message: EventMessage) -> None:
        """Inbound IPC envelope processing hook for parsing incoming Command/Event vectors.

        Args:
            message: Incoming EventMessage envelope.
        """
        pass

    @abstractmethod
    async def act(self) -> Optional[EventMessage]:
        """Core execution thread loop processing cognitive reasoning or evaluation passes.

        Returns:
            An optional EventMessage response to publish on the EventBus.
        """
        pass

    @abstractmethod
    async def report(self) -> EventMessage:
        """Broadcast finalized computational, audit, or metric matrices over the EventBus.

        Returns:
            An EventMessage report of final execution stats/results.
        """
        pass

    @abstractmethod
    async def checkpoint(self) -> str:
        """Serialize internal tracking state variables asynchronously down to the persistence layer.

        Returns:
            The reference address or checkpoint ID of the saved state.
        """
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Force immediate thread destruction, releasing active hooks safely."""
        pass
