"""Unit tests for Phase 3 global contracts.

Verifies instantiation and validation of WorkflowPlan and RuntimeResult.
"""

import os
import sys
import unittest
from pydantic import ValidationError

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from contracts.workflow import CapabilityProfile, TaskControlBlock, WorkflowNode, WorkflowPlan, RuntimeResult

class TestContracts(unittest.TestCase):
    """Test suite validating Phase 3 Contract schemas."""

    def test_workflow_plan_instantiation(self):
        """Verifies that WorkflowPlan and its children can be instantiated and validated."""
        cap_ref = CapabilityProfile(
            minimum_reasoning_tier="HIGH",
            needs_vision=False,
            needs_code_sandbox=True,
            context_window_minimum_k=32,
            cost_ceiling_usd=0.01
        )
        
        tcb = TaskControlBlock(
            workflow_id="W_123",
            assigned_runtime="COMPETITIVE",
            primary_capability=cap_ref,
            payload={"task_name": "database_migration"}
        )
        
        node = WorkflowNode(
            node_id="NODE_01",
            dependencies=[],
            tcb=tcb
        )
        
        plan = WorkflowPlan(
            workflow_id="W_123",
            version="1.0.0",
            compiler_version="1.2.0",
            policy_version="1.2.0",
            runtime_version="1.2.0",
            nodes={"NODE_01": node},
            risk_score=0.2,
            policy_flag="OK"
        )

        self.assertEqual(plan.workflow_id, "W_123")
        self.assertEqual(plan.nodes["NODE_01"].tcb.assigned_runtime, "COMPETITIVE")
        self.assertEqual(plan.compiler_version, "1.2.0")

    def test_runtime_result_validation(self):
        """Verifies that RuntimeResult parses correct typing envelopes."""
        res = RuntimeResult(
            output="Execution complete.",
            winner="Worker X",
            confidence=0.9,
            reason="Pass 1 validation complete.",
            provider="groq",
            model="llama-3.3-70b-versatile",
            token_usage={"prompt_tokens": 120, "completion_tokens": 80},
            estimated_cost_usd=0.0002,
            latency_ms=120.5,
            runtime_type="COMPETITIVE"
        )
        
        self.assertEqual(res.winner, "Worker X")
        self.assertEqual(res.token_usage["prompt_tokens"], 120)
        self.assertEqual(res.latency_ms, 120.5)

        # Test validation error on missing required field (e.g. missing output)
        with self.assertRaises(ValidationError):
            RuntimeResult(
                winner="Worker X",
                confidence=0.9,
                reason="Pass 1 validation complete.",
                provider="groq",
                model="llama-3.3-70b-versatile",
                runtime_type="COMPETITIVE"
            )

if __name__ == "__main__":
    unittest.main()
