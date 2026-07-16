import json
import logging
import os
import aiofiles
from typing import Dict, Any, List

logger = logging.getLogger("neelvak_analytics")

class RuntimeAnalytics:
    """Aggregates finished transaction footprints and calculates optimization targets.
    
    Includes a Human Approval Gate invariant preventing automated modification of
    production configuration. All suggestions are dumped to a staging file.
    """

    def __init__(self, candidates_path: str = "workspace/optimization_candidates.json"):
        self.candidates_path = candidates_path
        self._history: List[Dict[str, Any]] = []
        os.makedirs(os.path.dirname(self.candidates_path), exist_ok=True)
        self.active_weights = {"default_budget": 1.0, "timeout_strictness": 1.0}
        
    def record_transaction(self, workflow_id: str, tokens: int, cost: float, latency_ms: float, error_occured: bool):
        """Records a transaction footprint. Matches legacy signature."""
        transaction = {
            "actuals": {
                "estimated_cost_usd": cost,
                "latency_ms": latency_ms,
                "tokens": tokens,
                "error": error_occured
            },
            "estimates": {
                "estimated_cost_usd": cost * 0.9, # Mock estimate for analysis
                "latency_ms": latency_ms * 0.9
            }
        }
        self._history.append(transaction)
        logger.info(f"Analytics: Transaction recorded. Latency={latency_ms}ms, Cost=${cost}")

    def compute_optimization_vectors(self) -> None:
        """Parses performance logs to generate algorithmic parameter adjustments.
        
        Outputs candidate vectors to the staging file.
        Matches gateway/server.py method name.
        """
        import asyncio
        candidates = []
        
        # Heuristic 1: Token Burn tracking > 20% higher than compiler estimates
        total_actual_cost = sum(t["actuals"].get("estimated_cost_usd", 0) for t in self._history)
        total_est_cost = sum(t["estimates"].get("estimated_cost_usd", 0) for t in self._history)
        
        if total_est_cost > 0 and total_actual_cost > (total_est_cost * 1.20):
            candidates.append({
                "rule": "Budget Weight Scale Reduction",
                "reason": f"Actual cost (${total_actual_cost:.4f}) is > 20% over estimates (${total_est_cost:.4f})",
                "action": "Reduce compiler default budget threshold by 15%",
                "status": "PENDING_HUMAN_APPROVAL"
            })
            
        # Heuristic 2: Latency deviations
        total_actual_latency = sum(t["actuals"].get("latency_ms", 0) for t in self._history)
        total_est_latency = sum(t["estimates"].get("latency_ms", 0) for t in self._history)
        
        if total_est_latency > 0 and total_actual_latency > (total_est_latency * 1.50):
            candidates.append({
                "rule": "Runtime Timeout Strictness Increase",
                "reason": f"Actual latency ({total_actual_latency:.2f}ms) is > 50% over estimates ({total_est_latency:.2f}ms)",
                "action": "Increase strictness of Scheduler timeout triggers by 25%",
                "status": "PENDING_HUMAN_APPROVAL"
            })
            
        if candidates:
            # Call synchronous file write for compatibility if needed
            self._stage_optimization_candidates_sync(candidates)

    def _stage_optimization_candidates_sync(self, candidates: List[Dict[str, Any]]):
        """Writes candidates to the staging file (The Human Approval Gate)."""
        logger.info(f"Analytics: Staging {len(candidates)} optimization candidates.")
        try:
            existing = []
            if os.path.exists(self.candidates_path):
                with open(self.candidates_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        existing = json.loads(content)
                        
            existing.extend(candidates)
            
            with open(self.candidates_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(existing, indent=2))
        except Exception as e:
            logger.error(f"Failed to write optimization candidates: {e}")

    def approve_pending_calibrations(self) -> bool:
        """Approves candidates and updates weights."""
        try:
            if os.path.exists(self.candidates_path):
                with open(self.candidates_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        existing = json.loads(content)
                        for c in existing:
                            if "Budget Weight Scale Reduction" in c["rule"]:
                                self.active_weights["default_budget"] *= 0.85
                            elif "Runtime Timeout Strictness" in c["rule"]:
                                self.active_weights["timeout_strictness"] *= 1.25
                # Clear staging file
                with open(self.candidates_path, 'w', encoding='utf-8') as f:
                    f.write("[]")
            return True
        except Exception:
            return False
