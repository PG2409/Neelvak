"""Execution, Cost, and Capability Planners.

Optimizes execution ordering, budget allocations, and capability matches.
"""

import logging
import copy
from typing import List, Dict, Set, Any
from contracts.workflow import WorkflowPlan, WorkflowNode

logger = logging.getLogger("neelvak_kernel")

class ExecutionPlanner:
    """Arranges WorkflowPlan nodes into sequential levels of execution based on dependencies."""

    def plan_execution_layers(self, plan: WorkflowPlan) -> List[Dict[str, Any]]:
        """Calculates dependency layers to run independent nodes concurrently.

        Returns:
            List of dictionaries containing 'nodes' (List[str]) and 'parallel' (bool).
        """
        logger.info("Computing execution layer sequencing.")
        resolved: Set[str] = set()
        unresolved = set(plan.nodes.keys())
        layers: List[Dict[str, Any]] = []

        while unresolved:
            current_layer = []
            for node_id in list(unresolved):
                node = plan.nodes[node_id]
                # Check if all dependencies have been resolved in previous layers
                if all(dep in resolved for dep in node.dependencies):
                    current_layer.append(node_id)
            
            if not current_layer:
                # Cycle detected
                logger.critical("Dependency loop detected in WorkflowPlan topology.")
                raise ValueError("Cyclic dependency in workflow execution graph.")
                
            layers.append({
                "nodes": current_layer,
                "parallel": len(current_layer) > 1
            })
            resolved.update(current_layer)
            unresolved.difference_update(current_layer)

        logger.info(f"Layer sequencing completed. Total levels: {len(layers)}")
        return layers


class CostOptimizer:
    """Adjusts capability tiers dynamically based on remaining budget parameters."""

    def __init__(self, critical_threshold: float = 0.01) -> None:
        self.critical_threshold = critical_threshold

    def optimize_plan_budgets(self, plan: WorkflowPlan, remaining_budget: float) -> WorkflowPlan:
        """Scales capability requirements down if the global budget runs thin. Returns a new plan.

        Args:
            plan: The WorkflowPlan to modify.
            remaining_budget: Cash remaining in the session.
            
        Returns:
            A new WorkflowPlan with adjusted budgets (immutable operation).
        """
        logger.info(f"Checking cost allocations against remaining budget: ${remaining_budget:.4f}")
        if remaining_budget >= self.critical_threshold:
            return plan

        logger.warning("Remaining budget is critical! Downgrading high-tier nodes to low-cost alternatives.")
        new_plan = copy.deepcopy(plan)
        # Downgrade reasoning requirements
        for node in new_plan.nodes.values():
            tcb = node.tcb
            
            # If completely depleted, shift to zero-overhead DIRECT mode
            if remaining_budget <= 0.0:
                logger.info(f"CostOptimizer: Wallet depleted. Shifting node {node.node_id} to DIRECT zero-overhead mode.")
                tcb.assigned_runtime = "DIRECT"
                tcb.primary_capability.minimum_reasoning_tier = "LOW"
                tcb.primary_capability.cost_ceiling_usd = 0.0
                if tcb.adversarial_capability:
                    tcb.adversarial_capability.minimum_reasoning_tier = "LOW"
                    tcb.adversarial_capability.cost_ceiling_usd = 0.0
            # Otherwise, downgrade to standard
            elif tcb.primary_capability.minimum_reasoning_tier in ["HIGH", "DEEP_REASONING"]:
                logger.info(f"CostOptimizer: Downgrading node {node.node_id} reasoning tier to STANDARD.")
                tcb.primary_capability.minimum_reasoning_tier = "STANDARD"
                tcb.primary_capability.cost_ceiling_usd = 0.005
                if tcb.assigned_runtime == "COMPETITIVE":
                    tcb.assigned_runtime = "STANDARD"
            
            if remaining_budget > 0.0 and tcb.adversarial_capability and tcb.adversarial_capability.minimum_reasoning_tier in ["HIGH", "DEEP_REASONING"]:
                tcb.adversarial_capability.minimum_reasoning_tier = "STANDARD"
                tcb.adversarial_capability.cost_ceiling_usd = 0.005
                
        return new_plan


class CapabilityPlanner:
    """Profiles task intents to map required hardware settings (vision, code sandbox)."""

    def profile_task_requirements(self, task_name: str) -> Dict[str, Any]:
        """Profiles task name string to detect system tool capability requirements."""
        needs_vision = any(term in task_name.lower() for term in ["image", "plot", "render", "vision", "draw", "photo"])
        needs_sandbox = any(term in task_name.lower() for term in ["run", "execute", "eval", "python", "bash", "sandbox", "code"])
        
        flags = []
        if needs_vision:
            flags.append("VISION")
        if needs_sandbox:
            flags.append("CODE_SANDBOX")
            
        return {
            "needs_vision": needs_vision,
            "needs_code_sandbox": needs_sandbox,
            "resource_flags": flags
        }
