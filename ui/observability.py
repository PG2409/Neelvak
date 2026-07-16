import json
import logging
import os
import time
import asyncio
import collections
from typing import Dict, Any, List
from contracts.message import EventMessage

logger = logging.getLogger("neelvak_observability")

class ObservabilityService:
    """Connects to the EventBus to collect prioritized traces.
    
    Collects COMMAND, EVENT, and TOOL_AUDIT messages and aggregates them
    into a unified chronological timeline file.
    """
    
    def __init__(self, event_bus: Any, timeline_path: str = "workspace/telemetry_timeline.json"):
        self.event_bus = event_bus
        self.timeline_path = timeline_path
        self._timeline = collections.deque(maxlen=1000)
        self._lock = asyncio.Lock()
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self.timeline_path), exist_ok=True)
        
        # Initialize empty file if not exists
        if not os.path.exists(self.timeline_path):
            with open(self.timeline_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    async def start(self):
        """Starts the observability service and subscribes to the event bus."""
        await self.event_bus.subscribe("COMMAND", self._handle_event)
        await self.event_bus.subscribe("EVENT", self._handle_event)
        await self.event_bus.subscribe("TOOL_AUDIT", self._handle_event)
        logger.info("ObservabilityService started and connected to EventBus.")

    async def _handle_event(self, message: EventMessage):
        """Callback for incoming event bus messages."""
        entry = {
            "event_id": message.event_id,
            "workflow_id": message.workflow_id,
            "timestamp": message.timestamp,
            "source": message.source,
            "event_type": message.event_type,
            "priority": message.priority,
            "payload": message.payload,
            "status": message.status,
            "duration_ms": message.duration_ms,
        }
        async with self._lock:
            self._timeline.append(entry)
            # In a real heavy-load system, this might batch-flush.
            # We append directly for deterministic chronological order.
            await self._flush_to_disk()

    async def _flush_to_disk(self):
        """Writes the updated timeline array to disk."""
        import aiofiles
        try:
            # We overwrite with the full timeline array
            async with aiofiles.open(self.timeline_path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(list(self._timeline), indent=2))
        except Exception as e:
            logger.error(f"Failed to flush telemetry timeline: {e}")

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Returns the current ordered timeline."""
        return list(self._timeline)
