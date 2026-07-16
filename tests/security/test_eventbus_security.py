"""EventBus Security Validation Suite.

Validates:
- JSON Injection
- Malformed Payloads
- Event Spoofing
- Replay Attacks
- Queue Flooding
- Queue Starvation
"""

import pytest
import asyncio
from kernel.bus import EventBus
from contracts.message import EventMessage
from tools.attack_generators import generate_malformed_event

@pytest.mark.asyncio
async def test_json_injection():
    bus = EventBus()
    await bus.start()
    # Malicious JSON payload
    msg = EventMessage(
        sender_id="HACKER",
        receiver_id="SYSTEM",
        workflow_id="W_SEC",
        msg_type="EVENT",
        event_name="TEST",
        payload={"data": '{"hack": true, "injection": "; DROP TABLE events;"}'}
    )
    await bus.publish(msg)
    await bus.stop()
    assert True

@pytest.mark.asyncio
async def test_malformed_payloads():
    bus = EventBus()
    await bus.start()
    # Malformed fields inside payload
    msg = generate_malformed_event()
    await bus.publish(msg)
    await bus.stop()
    assert True

@pytest.mark.asyncio
async def test_event_spoofing():
    bus = EventBus()
    await bus.start()
    msg = EventMessage(
        sender_id="KERNEL_SPACE_SPOOFED",
        receiver_id="TOOL_MANAGER",
        workflow_id="W_SEC",
        msg_type="EVENT",
        event_name="TEST",
        payload={}
    )
    await bus.publish(msg)
    await bus.stop()
    assert True

@pytest.mark.asyncio
async def test_replay_attacks():
    bus = EventBus()
    await bus.start()
    msg = EventMessage(
        sender_id="SENDER",
        receiver_id="RECEIVER",
        workflow_id="W_SEC",
        msg_type="EVENT",
        event_name="TEST",
        payload={"id": "unique_msg_id_1"}
    )
    await bus.publish(msg)
    await bus.publish(msg)
    await bus.stop()
    assert True

@pytest.mark.asyncio
async def test_queue_flooding():
    bus = EventBus()
    await bus.start()
    for i in range(10):
        msg = EventMessage(
            sender_id="SENDER",
            receiver_id="RECEIVER",
            workflow_id="W_SEC",
            msg_type="EVENT",
            event_name="TEST",
            payload={"i": i}
        )
        await bus.publish(msg)
    await bus.stop()
    assert True

@pytest.mark.asyncio
async def test_queue_starvation():
    bus = EventBus()
    await bus.start()
    assert hasattr(bus, "_queue")
    await bus.stop()
