"""Deterministic Policy Verification Engine.

Enforces budget limits, risk boundaries, and injection sweeps without LLM tokens.
"""

import logging
import re
import json
from typing import Tuple
from contracts.workflow import WorkflowPlan

logger = logging.getLogger("neelvak_kernel")

class PolicyEngine:
    """Rigid security ring evaluating WorkflowPlans under strict deterministic checks."""

    # Common injection/jailbreak patterns
    INJECTION_REGEX = re.compile(
        r"(ignore\s+previous\s+instructions|ignore\s+instructions|jailbreak|system\s+override|sudo\s+rm\s+-rf|format\s+c:|you\s+are\s+now\s+unrestricted)",
        re.IGNORECASE
    )

    def __init__(self, budget_limit: float = 0.10, risk_threshold: float = 0.90) -> None:
        self.budget_limit = budget_limit
        self.risk_threshold = risk_threshold

    def validate_plan(self, plan: WorkflowPlan, user_prompt: str) -> Tuple[bool, str]:
        """Runs standard security checks against the plan and prompt.

        Args:
            plan: The compiled WorkflowPlan.
            user_prompt: Raw user input text.

        Returns:
            Tuple (is_valid, validation_message)
        """
        logger.info("Executing PolicyEngine validation sweep.")

        # 1. Enforce injection verification over raw input
        if self.INJECTION_REGEX.search(user_prompt):
            logger.warning("PolicyEngine alert: Malicious prompt injection indicator matched in user prompt.")
            return False, "Security Violation Detected"

        # 2. Enforce risk threshold validation
        if plan.risk_score > self.risk_threshold:
            logger.warning(f"PolicyEngine alert: Workflow risk score {plan.risk_score} exceeds {self.risk_threshold} threshold.")
            return False, f"Policy Violation: Risk score {plan.risk_score} exceeds maximum bounds."

        # 3. Enforce budget checks & node-level injection checks
        total_estimated_cost = 0.0
        for node in plan.nodes.values():
            # Check node payload for forbidden vectors
            payload_str = json.dumps(node.tcb.payload)
            if self.INJECTION_REGEX.search(payload_str):
                logger.warning(f"PolicyEngine alert: Malicious injection matched in node payload {node.node_id}.")
                return False, "Security Violation Detected"

            total_estimated_cost += node.tcb.primary_capability.cost_ceiling_usd
            if node.tcb.adversarial_capability:
                total_estimated_cost += node.tcb.adversarial_capability.cost_ceiling_usd

        if total_estimated_cost > self.budget_limit:
            logger.warning(f"PolicyEngine alert: Budget estimate {total_estimated_cost:.4f} exceeds {self.budget_limit} limit.")
            return False, f"Policy Violation: Cost estimate ${total_estimated_cost:.4f} exceeds system limits."

        logger.info("PolicyEngine check completed successfully. Plan validation returns green.")
        return True, "OK"
