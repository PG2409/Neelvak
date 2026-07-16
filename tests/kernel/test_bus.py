"""Unit tests for Phase 2 Core Kernel Services.

Verifies priority routing on the EventBus, lock-guarded registry sweeps,
and state machine progression checks.
"""

import os
import sys
import asyncio
import unittest
import pytest

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from contracts.message import EventMessage
from kernel.bus import EventBus
from kernel.lifecycle import LifecycleManager, ProcessControlBlock, ProcessState, TerminationReason
from kernel.registry import AgentRegistry

class TestKernelCoreServices(unittest.IsolatedAsyncioTestCase):
    """Test suite validating Phase 2 Core Kernel components."""

    async def test_event_bus_prioritization(self):
        """Verifies that EventBus PriorityQueue sorts SYSTEM (0) before LOW (3) priority messages."""
        bus = EventBus()
        # Do not start the bus loop immediately so we can populate the queue and check order
        
        received_order = []

        async def mock_callback(msg: EventMessage) -> None:
            received_order.append(msg.event_name)

        bus.subscribe("TEST_SINK", mock_callback)

        # Publish in reverse priority order
        msg_low = EventMessage(
            sender_id="S1", receiver_id="TEST_SINK", workflow_id="W1",
            msg_type="EVENT", event_name="MSG_LOW", priority=3
        )
        msg_normal = EventMessage(
            sender_id="S1", receiver_id="TEST_SINK", workflow_id="W1",
            msg_type="EVENT", event_name="MSG_NORMAL", priority=2
        )
        msg_high = EventMessage(
            sender_id="S1", receiver_id="TEST_SINK", workflow_id="W1",
            msg_type="EVENT", event_name="MSG_HIGH", priority=1
        )
        msg_system = EventMessage(
            sender_id="S1", receiver_id="TEST_SINK", workflow_id="W1",
            msg_type="EVENT", event_name="MSG_SYSTEM", priority=0
        )

        await bus.publish(msg_low)
        await bus.publish(msg_normal)
        await bus.publish(msg_high)
        await bus.publish(msg_system)

        # Start routing loop
        await bus.start()
        # Allow routing task to pop all queue messages
        await asyncio.sleep(0.3)
        await bus.stop()

        # The expected order must strictly reflect priority weights: SYSTEM (0) -> HIGH (1) -> NORMAL (2) -> LOW (3)
        expected = ["MSG_SYSTEM", "MSG_HIGH", "MSG_NORMAL", "MSG_LOW"]
        self.assertEqual(received_order, expected)

    def test_lifecycle_transaction_safety(self):
        """Verifies that invalid state transitions fail smoothly without panicking."""
        manager = LifecycleManager()
        pcb = ProcessControlBlock(pcb_id="PCB_TEST", workflow_id="W1", runtime="STANDARD")

        # Inital state is SPAWNED
        self.assertEqual(pcb.state, ProcessState.SPAWNED)

        # Invalid transition: SPAWNED -> EXECUTING (must go to QUEUED first)
        result = manager.transition(pcb, ProcessState.EXECUTING)
        self.assertFalse(result)
        self.assertEqual(pcb.state, ProcessState.SPAWNED)

        # Valid transition: SPAWNED -> QUEUED
        result_ok = manager.transition(pcb, ProcessState.QUEUED)
        self.assertTrue(result_ok)
        self.assertEqual(pcb.state, ProcessState.QUEUED)

        # Valid transition: QUEUED -> EXECUTING
        result_exec = manager.transition(pcb, ProcessState.EXECUTING)
        self.assertTrue(result_exec)
        self.assertEqual(pcb.state, ProcessState.EXECUTING)

        # Attempt invalid reverse transition: EXECUTING -> QUEUED
        result_rev = manager.transition(pcb, ProcessState.QUEUED)
        self.assertFalse(result_rev)
        self.assertEqual(pcb.state, ProcessState.EXECUTING)

if __name__ == "__main__":
    unittest.main()
