"""Model Selector Logic.

Uses the CSS profile from CostEngine to select the optimal model from the catalogue.
"""

import logging
from typing import Dict, Any, Tuple
import config

logger = logging.getLogger("neelvak_kernel")

class ModelSelector:
    """Maps CSS profiles to physical models based on the capability catalogue."""

    def select(self, css_profile: Dict[str, Any]) -> Tuple[str, str, str]:
        """Selects the best model for a given CSS profile.
        
        Args:
            css_profile: The 4-score profile from CostEngine.
            
        Returns:
            Tuple of (provider, model_name, tier_name)
        """
        lane = css_profile.get("lane", "C")
        
        # Map lane to config catalogue tier
        tier_mapping = {
            "A": "tier_3_frontier",
            "B": "tier_2_reasoning",
            "C": "tier_1_fast",
            "D": "tier_1_fast" # Fallback to fast tier if micro isn't defined explicitly
        }
        
        tier = tier_mapping.get(lane, "tier_1_fast")
        
        # Retrieve from catalogue
        catalogue_entry = config.CAPABILITY_CATALOGUE.get(tier)
        
        if not catalogue_entry or not catalogue_entry.get("routing_chain"):
            # Ultimate fallback
            logger.warning(f"ModelSelector: Tier {tier} not found or empty in catalogue. Using fallback.")
            return "groq", "llama-3.1-8b-instant", "tier_1_fast"
            
        # For prototype, just pick the primary (index 0) model in the routing chain
        # In a full implementation, we'd check health status and fallback down the chain
        primary_model = catalogue_entry["routing_chain"][0]
        
        provider = primary_model["provider"]
        model = primary_model["model"]
        
        logger.info(f"ModelSelector: Mapped Lane {lane} to Tier {tier} -> {provider}/{model}")
        return provider, model, tier
