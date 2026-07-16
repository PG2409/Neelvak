"""Cost Optimization Engine.

Implements the 4-Score Context Sufficiency Score (CSS) routing logic to 
determine the cheapest, fastest model capable of handling a specific prompt.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("neelvak_kernel")

class CostEngine:
    """Evaluates prompts to assign a 4-Score CSS profile."""

    def __init__(self):
        # Keywords that suggest high reasoning complexity
        self.complex_keywords = [
            "analyze", "synthesize", "architect", "design", "evaluate",
            "debug", "explain why", "compare", "contrast", "optimize",
            "algorithm", "system", "infrastructure"
        ]

    def evaluate(self, prompt: str, token_estimate: int) -> Dict[str, Any]:
        """Generate a 4-Score CSS profile for a given prompt.
        
        Args:
            prompt: The user prompt.
            token_estimate: Estimated token count of the prompt + context.
            
        Returns:
            Dict containing the 4 scores:
            - cost_score: Expected cost tier based on tokens.
            - complexity_score: 0.0 to 1.0 based on reasoning depth required.
            - confidence_score: 0.0 to 1.0 based on how well the prompt is understood.
            - runtime_score: Which A-E lane this belongs in.
        """
        # 1. Complexity Score (Heuristic)
        prompt_lower = prompt.lower()
        complexity = 0.2  # Base complexity for trivial tasks (e.g. "hello")
        
        for kw in self.complex_keywords:
            if kw in prompt_lower:
                complexity += 0.15
                
        # Length also implies complexity (very rough heuristic)
        if len(prompt) > 500:
            complexity += 0.2
            
        complexity = min(max(complexity, 0.0), 1.0)
        
        # 2. Cost Score (Token Based)
        # Higher score means higher expected cost
        cost_score = min(token_estimate / 10000.0, 1.0) 
        
        # 3. Confidence Score
        # How confident are we that we understand the intent?
        # Short, clear prompts -> high confidence. Ambiguous -> lower.
        words = len(prompt.split())
        if 5 <= words <= 50:
            confidence = 0.9
        elif words < 5:
            confidence = 0.6 # Too short, maybe ambiguous
        else:
            confidence = 0.7 # Very long, might have multiple conflicting intents
            
        # 4. Runtime Lane Score
        if complexity > 0.8:
            lane = "A" # Frontier Cloud (e.g. Claude 3.5 Sonnet / GPT-4o)
        elif complexity > 0.5:
            lane = "B" # Fast Cloud (e.g. Llama 3 70B / Mixtral)
        elif complexity > 0.3:
            lane = "C" # Edge Cloud (e.g. Llama 3 8B)
        else:
            lane = "D" # Local/Micro (e.g. Local Phi-3)
            
        profile = {
            "complexity": round(complexity, 2),
            "cost": round(cost_score, 2),
            "confidence": round(confidence, 2),
            "lane": lane
        }
        
        logger.info(f"CostEngine: CSS Profile generated: {profile}")
        return profile
