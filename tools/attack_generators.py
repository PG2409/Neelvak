"""Generators for fuzzing objects."""
from contracts.message import EventMessage
from tools.malicious_payloads import OVERSIZE_PAYLOAD

def generate_malformed_event() -> EventMessage:
    """Generates an event message with corrupt fields to test EventBus resilience."""
    return EventMessage(
        sender_id="HACKER",
        receiver_id="SYSTEM",
        workflow_id="123",
        msg_type="EVENT",
        event_name="BOMB",
        payload={"data": OVERSIZE_PAYLOAD}
    )
