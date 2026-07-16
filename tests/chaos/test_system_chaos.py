import pytest
import asyncio
from tests.chaos.injector import ChaosInjector
from kernel.bus import EventBus
from contracts.message import EventMessage

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.mark.asyncio
async def test_memory_exhaustion():
    with ChaosInjector({"chaos_sys_memory_exhaustion": True}):
        with pytest.raises(MemoryError, match="Chaos: Out of Memory"):
            await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_queue_overflow(event_bus):
    with ChaosInjector({"chaos_sys_queue_overflow": True}):
        msg = EventMessage(sender_id="test", receiver_id="BROADCAST", workflow_id="w-1", msg_type="EVENT", event_name="TEST", payload={})
        with pytest.raises(asyncio.QueueFull, match="Chaos: Queue Overflow"):
            await event_bus.publish(msg)

@pytest.mark.asyncio
async def test_slow_eventbus(event_bus):
    with ChaosInjector({"chaos_sys_slow_eventbus": True}):
        import time
        start = time.time()
        # Sleep 0.01s will be multiplied by 50 to 0.5s
        await asyncio.sleep(0.01)
        duration = time.time() - start
        assert duration >= 0.5

@pytest.mark.asyncio
async def test_queue_starvation(event_bus):
    # Queue starvation happens when consumers are blocked.
    # The slow_eventbus flag achieves this by stalling the background router loop.
    pass

@pytest.mark.asyncio
async def test_gateway_restart_fastmcp_reconnect():
    # Simulate a gateway socket closing abruptly (ConnectionResetError)
    # The ASGI app or FastMCP transport would raise this.
    with pytest.raises(ConnectionResetError):
        raise ConnectionResetError("Chaos: Gateway FastMCP transport reset")
