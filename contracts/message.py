"""CQRS Command/Event Pydantic Schemas.

Defines the message envelopes for async IPC over the microkernel event bus.
"""

import time
import uuid
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field

class EventMessage(BaseModel):
    """Pydantic model representing a message routed over the CQRS Event Bus."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: str  # PCB ID or "BROADCAST"
    workflow_id: str
    msg_type: Literal["COMMAND", "EVENT"]
    event_name: str
    priority_weight: int = 2  # SYSTEM=0, HIGH=1, NORMAL=2, LOW=3
    priority: int = 2  # SYSTEM=0, HIGH=1, NORMAL=2, LOW=3 (Compatibility field)
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Observability phase 1 fields
    status: str = "success"
    duration_ms: float = 0.0

    @property
    def event_id(self) -> str:
        return self.message_id

    @property
    def source(self) -> str:
        return self.sender_id

    @property
    def event_type(self) -> str:
        return self.event_name
