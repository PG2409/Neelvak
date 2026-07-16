"""Asynchronous CQRS Event Bus Broker.

Facilitates inter-process communications over isolated channels using a PriorityQueue.
"""

import asyncio
import logging
from typing import Dict, List, Callable, Awaitable, Optional
from contracts.message import EventMessage

logger = logging.getLogger("neelvak_kernel")

class EventBus:
    """Asynchronous CQRS Event Bus executing serialization and prioritized routing of messages."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._subscribers: Dict[str, List[Callable[[EventMessage], Awaitable[None]]]] = {}
        self._running: bool = False
        self._loop_task: Optional[asyncio.Task] = None
        self._dispatching_count: int = 0

    async def start(self) -> None:
        """Starts the asynchronous background event routing loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._route_loop())
        logger.info("EventBus started and prioritized routing loops operational.")

    async def stop(self) -> None:
        """Stops the background loop and clears active connections."""
        self._running = False
        # Wait for all active dispatches to finish processing
        while self._dispatching_count > 0:
            await asyncio.sleep(0.01)
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._subscribers.clear()
        logger.info("EventBus stopped.")

    async def publish(self, message: EventMessage) -> None:
        """Pushes a message onto the prioritized queue channel.

        Items are stored as a tuple (priority, timestamp, message_id, message)
        to prevent comparison on Pydantic models.

        Args:
            message: The message envelope to publish.
        """
        # Lower integer priority values are fetched first by PriorityQueue
        await self._queue.put((message.priority, message.timestamp, message.message_id, message))
        logger.debug(f"Published message: {message.message_id} [Priority: {message.priority}]")

    def subscribe(self, receiver_id: str, callback: Callable[[EventMessage], Awaitable[None]]) -> None:
        """Registers an asynchronous callback for a specific subscriber address.

        Args:
            receiver_id: Unique subscriber ID or 'BROADCAST'.
            callback: Async callback executed upon message receipt.
        """
        if receiver_id not in self._subscribers:
            self._subscribers[receiver_id] = []
        self._subscribers[receiver_id].append(callback)
        logger.debug(f"Subscribed callback to receiver ID: {receiver_id}")

    def unsubscribe(self, receiver_id: str, callback: Callable[[EventMessage], Awaitable[None]]) -> None:
        """Removes a previously registered asynchronous callback.

        Args:
            receiver_id: Unique subscriber ID or 'BROADCAST'.
            callback: Async callback to remove.
        """
        if receiver_id in self._subscribers:
            try:
                self._subscribers[receiver_id].remove(callback)
                logger.debug(f"Unsubscribed callback from receiver ID: {receiver_id}")
                if not self._subscribers[receiver_id]:
                    del self._subscribers[receiver_id]
            except ValueError:
                pass

    async def _route_loop(self) -> None:
        """Worker loop processing messages sorted by priority and dispatching them."""
        while self._running:
            try:
                # Retrieve from priority queue
                priority, timestamp, msg_id, message = await self._queue.get()
                
                # Resolve active receivers
                destinations = []
                if message.receiver_id == "BROADCAST":
                    # Broadcast to all distinct channels
                    for channels in self._subscribers.values():
                        destinations.extend(channels)
                else:
                    destinations.extend(self._subscribers.get(message.receiver_id, []))
                
                # Dispatch concurrently to insulate channels
                if destinations:
                    self._dispatching_count += 1
                    try:
                        if len(destinations) == 1:
                            await destinations[0](message)
                        else:
                            await asyncio.gather(*[cb(message) for cb in destinations], return_exceptions=True)
                    finally:
                        self._dispatching_count -= 1
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventBus dispatch error: {e}")
                await asyncio.sleep(0.1)
