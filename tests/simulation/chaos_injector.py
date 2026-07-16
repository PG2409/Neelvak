"""Chaos Injector.

Simulates catastrophic events in the Neelvak AIOS runtime including:
- Dropping/delaying EventBus messages.
- Corrupting checkpoints on disk.
- Task termination (simulated kill).
"""

import asyncio
import logging
import random
import os
import aiofiles
from typing import Any

from kernel.bus import EventBus
from contracts.message import EventMessage

logger = logging.getLogger("neelvak_chaos")

class ChaosInjector:
    """Injects faults across the system."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._original_publish = event_bus.publish
        self.drop_rate = 0.0
        self.delay_rate = 0.0
        self.max_delay_sec = 2.0
        
        self.messages_dropped = 0
        self.messages_delayed = 0

    def enable_event_bus_chaos(self, drop_rate: float = 0.05, delay_rate: float = 0.1, max_delay: float = 2.0):
        """Hooks into the EventBus to drop or delay messages."""
        self.drop_rate = drop_rate
        self.delay_rate = delay_rate
        self.max_delay_sec = max_delay
        
        async def chaotic_publish(message: EventMessage):
            # 1. Drop check
            if random.random() < self.drop_rate:
                self.messages_dropped += 1
                logger.warning(f"ChaosInjector: Dropped message {message.message_id} intentionally.")
                return # Message lost to the void
                
            # 2. Delay check
            if random.random() < self.delay_rate:
                self.messages_delayed += 1
                delay = random.uniform(0.1, self.max_delay_sec)
                logger.warning(f"ChaosInjector: Delaying message {message.message_id} by {delay:.2f}s.")
                await asyncio.sleep(delay)
                
            await self._original_publish(message)

        # Monkey-patch publish
        self.event_bus.publish = chaotic_publish
        logger.info("ChaosInjector: EventBus chaos enabled.")

    def disable_event_bus_chaos(self):
        self.event_bus.publish = self._original_publish
        logger.info("ChaosInjector: EventBus chaos disabled.")

    async def corrupt_checkpoint(self, directory: str = "data_store"):
        """Randomly picks an existing checkpoint JSON file and corrupts its schema."""
        if not os.path.exists(directory):
            return
            
        files = [f for f in os.listdir(directory) if f.startswith("checkpoint_") and f.endswith(".json")]
        if not files:
            return
            
        target = random.choice(files)
        path = os.path.join(directory, target)
        
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
                
            # Truncate halfway
            corrupted = content[:len(content)//2]
            
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(corrupted)
                
            logger.critical(f"ChaosInjector: Intentionally corrupted checkpoint {target}")
        except Exception as e:
            logger.error(f"ChaosInjector failed to corrupt checkpoint: {e}")
