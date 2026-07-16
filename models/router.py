"""Dynamic Capability-Aware Model Router.

Matches CapabilityProfiles from the compiler's IR_v4 DAG output to the optimal
entry in the CAPABILITY_CATALOGUE routing chains. The router is purely a
*selection* layer — it chooses which provider/model to use. Actual HTTP
execution is delegated to ``ProviderInterface``.

The router enforces:
  - Tier-weight matching (LOW → STANDARD → HIGH → DEEP_REASONING)
  - Vision capability filtering
  - Context window minimum filtering
  - Cost ceiling enforcement
  - Provider health awareness
  - Diversity enforcement across sibling workflow nodes
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from contracts.workflow import CapabilityProfile, ProviderDecision
from models.health import ProviderHealthManager, ProviderState
from models.provider import ProviderInterface
import config

logger = logging.getLogger("neelvak_kernel")

# Canonical tier weight lookup — used for >= comparisons
_TIER_WEIGHTS: Dict[str, int] = {
    "LOW": 1,
    "STANDARD": 2,
    "HIGH": 3,
    "DEEP_REASONING": 4,
}


class ModelRouter:
    """Selects providers and model strings dynamically from routing chains.

    After selection, runtime agents call ``ProviderInterface.execute()``
    directly, passing the chain returned by ``resolve_capability()`` for
    automatic failover.
    """

    def __init__(self, health_manager: ProviderHealthManager, event_bus: Optional[Any] = None) -> None:
        self.health_manager = health_manager
        self.event_bus = event_bus
        # Tracks providers assigned per workflow_id: {workflow_id: {provider_name, ...}}
        self.workflow_assignments: Dict[str, Set[str]] = {}
        # Shared ProviderInterface instance
        self.provider_interface = ProviderInterface(event_bus=self.event_bus)

    def resolve_capability(
        self, profile: CapabilityProfile, workflow_id: str
    ) -> ProviderDecision:
        """Resolves capability profile specifications to a healthy provider/model.

        Walks the entire ``CAPABILITY_CATALOGUE``, finds all tiers whose routing
        chains contain at least one model satisfying the profile constraints,
        and returns the best candidate as a ProviderDecision.

        Args:
            profile: Required execution capability constraints from the IR_v4.
            workflow_id: Tracking ID for diversity enforcement.

        Returns:
            ProviderDecision containing evaluation metrics and selected routing chain.
        """
        logger.info(
            f"ModelRouter: Resolving model for reasoning_tier={profile.minimum_reasoning_tier}, "
            f"vision={profile.needs_vision}, context>={profile.context_window_minimum_k}k, "
            f"cost<={profile.cost_ceiling_usd}, workflow={workflow_id}"
        )

        if workflow_id not in self.workflow_assignments:
            self.workflow_assignments[workflow_id] = set()

        used_providers = self.workflow_assignments[workflow_id]
        required_weight = _TIER_WEIGHTS.get(profile.minimum_reasoning_tier, 2)

        # Collect all candidate (tier_key, chain_entry, chain) tuples
        candidates: List[Tuple[str, Dict[str, Any], List[Dict[str, Any]]]] = []

        for tier_key, tier_def in config.CAPABILITY_CATALOGUE.items():
            tier_weight = _TIER_WEIGHTS.get(tier_def.get("tier", "STANDARD"), 2)
            if tier_weight < required_weight:
                continue

            chain = tier_def.get("routing_chain", [])
            for entry in chain:
                # Vision filter
                if profile.needs_vision and not entry.get("vision_capable", False):
                    continue
                # Context window filter
                if entry.get("context_window_k", 0) < profile.context_window_minimum_k:
                    continue
                # Cost ceiling filter (approximate per-request cost check)
                if entry.get("cost_per_1k", 0) * 10 > profile.cost_ceiling_usd:
                    continue
                # Health filter — skip fully OFFLINE providers
                if self.health_manager.get_status(entry["provider"]) == ProviderState.OFFLINE:
                    continue

                candidates.append((tier_key, entry, chain))

        if not candidates:
            logger.warning(
                "ModelRouter: No matching healthy candidates. "
                "Falling back to tier_2_standard chain head."
            )
            fallback_chain = config.CAPABILITY_CATALOGUE.get(
                "tier_2_standard", {}
            ).get("routing_chain", [])
            fb_provider = fallback_chain[0]["provider"] if fallback_chain else "groq"
            fb_model = fallback_chain[0]["model"] if fallback_chain else "llama-3.1-8b-instant"
            return ProviderDecision(
                reasoning_tier="STANDARD",
                context_window_k=8,
                vision_support=False,
                tool_support=True,
                budget_usd=profile.cost_ceiling_usd,
                estimated_latency_ms=1000.0,
                health_status="HEALTHY",
                quota_remaining=1000.0,
                historical_success_rate=1.0,
                historical_latency_ms=1000.0,
                queue_depth=0,
                estimated_cost_usd=0.001,
                fallback_rules_applied=True,
                selected_provider=fb_provider,
                selected_model=fb_model,
                routing_chain=fallback_chain
            )

        # Evaluate 13 factors for sorting
        def _evaluate_factors(item: Tuple[str, Dict[str, Any], List[Dict[str, Any]]]) -> Tuple:
            tier_key, entry, _ = item
            prov = entry["provider"]

            state = self.health_manager.get_status(prov)
            state_w = {
                ProviderState.HEALTHY: 0,
                ProviderState.RECOVERING: 1,
                ProviderState.DEGRADED: 2,
                ProviderState.OFFLINE: 3,
            }.get(state, 3)

            diversity_penalty = 1000 if (profile.diversity_group_id and prov in used_providers) else 0
            
            queue_depth = self.health_manager.get_queue_depth(prov)
            historical_success = self.health_manager.get_success_rate(prov)
            historical_latency = self.health_manager.get_historical_latency(prov)
            quota_remaining = self.health_manager.get_quota(prov)
            
            # Sort factors: health > quota > success > latency > diversity > cost > queue
            return (
                state_w,
                0 if quota_remaining > 0 else 1,
                -historical_success,  # higher is better
                diversity_penalty,
                historical_latency,
                entry.get("cost_per_1k", 999),
                queue_depth
            )

        candidates.sort(key=_evaluate_factors)

        best_tier_key, best_entry, best_chain = candidates[0]
        best_provider = best_entry["provider"]
        fallback_applied = len(candidates) < len(config.CAPABILITY_CATALOGUE)

        if profile.diversity_group_id and best_provider in used_providers:
            logger.warning(
                f"ModelRouter: Forced to reuse provider '{best_provider}' "
                f"despite diversity constraint."
            )

        self.workflow_assignments[workflow_id].add(best_provider)

        logger.info(
            f"ModelRouter: Selected '{best_tier_key}' → "
            f"provider='{best_provider}', model='{best_entry['model']}'."
        )
        
        decision = ProviderDecision(
            reasoning_tier=profile.minimum_reasoning_tier,
            context_window_k=best_entry.get("context_window_k", 8),
            vision_support=best_entry.get("vision_capable", False),
            tool_support=best_entry.get("tool_capable", True),
            budget_usd=profile.cost_ceiling_usd,
            estimated_latency_ms=self.health_manager.get_historical_latency(best_provider),
            health_status=self.health_manager.get_status(best_provider).value,
            quota_remaining=self.health_manager.get_quota(best_provider),
            historical_success_rate=self.health_manager.get_success_rate(best_provider),
            historical_latency_ms=self.health_manager.get_historical_latency(best_provider),
            queue_depth=self.health_manager.get_queue_depth(best_provider),
            estimated_cost_usd=best_entry.get("cost_per_1k", 0.0),
            fallback_rules_applied=fallback_applied,
            selected_provider=best_provider,
            selected_model=best_entry["model"],
            routing_chain=best_chain
        )
        
        # Publish decision
        if self.event_bus:
            import asyncio
            from contracts.message import EventMessage
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="ROUTER",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="ProviderDecision",
                payload=decision.model_dump()
            )))
            
        return decision

    def purge_workflow(self, workflow_id: str) -> None:
        """Purge tracking records for a completed workflow to prevent memory leakage."""
        if workflow_id in self.workflow_assignments:
            del self.workflow_assignments[workflow_id]
            logger.info(f"ModelRouter: Purged assignments for workflow {workflow_id}")
