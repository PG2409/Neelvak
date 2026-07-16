"""Token Sliding-Window Packing Engine.

Maintains context budget window caps and executes semantic context compression passes.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("neelvak_kernel")

class ContextManager:
    """Manages conversational history, token packing, and window compression."""

    def __init__(self, max_tokens: int = 4096) -> None:
        self.max_tokens = max_tokens
        self._history: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str, pinned: bool = False) -> None:
        """Appends a dialogue trace block to historical tracking.

        Args:
            role: "user" | "assistant" | "system"
            content: Text payload.
            pinned: Whether to lock this message in context.
        """
        self._history.append({"role": role, "content": content, "pinned": pinned})
        logger.debug(f"ContextManager added message for role: {role}")

    def _estimate_tokens(self, text: str) -> int:
        """Deterministic token metric calculator (estimate 1 token ≈ 4 characters)."""
        return max(1, len(text) // 4)

    def pack_context(self) -> List[Dict[str, Any]]:
        """Packs messages under sliding-window constraints, preserving system/pinned rules."""
        if not self._history:
            return []
            
        # 1. Identify items that MUST be preserved
        must_preserve = []
        token_sum = 0
        
        # System prompts and pinned messages
        for msg in self._history:
            is_system = msg.get("role") == "system"
            is_pinned = msg.get("pinned", False) or "[PIN]" in msg.get("content", "")
            if is_system or is_pinned:
                must_preserve.append(msg)
                token_sum += self._estimate_tokens(msg.get("content", ""))

        # The immediate user query (last message)
        last_msg = self._history[-1] if self._history else None
        has_last_msg_in_must = last_msg in must_preserve
        
        if last_msg and not has_last_msg_in_must:
            last_tokens = self._estimate_tokens(last_msg.get("content", ""))
            token_sum += last_tokens
            
        # 2. Add intermediate messages in reverse order until we hit the token ceiling
        retained_intermediates = []
        for msg in reversed(self._history):
            if msg in must_preserve or msg is last_msg:
                continue
                
            msg_tokens = self._estimate_tokens(msg.get("content", ""))
            if token_sum + msg_tokens <= self.max_tokens:
                token_sum += msg_tokens
                retained_intermediates.insert(0, msg)
            else:
                logger.warning("Context Window limit reached. Older intermediate history truncated.")
                break
                
        # Reconstruct sequence in chronological order
        result = []
        for msg in self._history:
            if msg in must_preserve or msg in retained_intermediates or (msg is last_msg and not has_last_msg_in_must):
                result.append(msg)
                
        return result

    def compress_history_deterministic(self) -> None:
        """Applies a deterministic text summary parsing block over old logs."""
        if len(self._history) < 4:
            return
            
        logger.info("Triggering sliding-window deterministic compression pass.")
        system = [m for m in self._history if m.get("role") == "system"]
        others = [m for m in self._history if m.get("role") != "system"]
        
        if len(others) <= 2:
            return

        to_compress = others[:-2]
        retained = others[-2:]

        # Simple deterministic compression: merge and take key sentences
        merged_text = " ".join([m.get("content", "") for m in to_compress])
        sentences = merged_text.split(". ")
        
        # Take every second sentence to collapse content size by 50%
        compressed_text = ". ".join(sentences[::2])
        if compressed_text and not compressed_text.endswith("."):
            compressed_text += "."

        summary_msg = {
            "role": "system",
            "content": f"[Context Compressed Summary]: {compressed_text}",
            "pinned": True
        }

        self._history = system + [summary_msg] + retained
        logger.info("Context deterministic compression completed.")

    async def compress_history_semantic(self, optimize: bool = False) -> None:
        """Applies semantic compression calling a fast 8B model if optimization is True."""
        if not optimize or len(self._history) < 4:
            # Fall back to default deterministic compression
            self.compress_history_deterministic()
            return

        logger.info("Executing async semantic history compression pass utilizing fast 8B coprocessor.")
        
        system = [m for m in self._history if m.get("role") == "system"]
        others = [m for m in self._history if m.get("role") != "system"]
        
        if len(others) <= 2:
            return

        to_compress = others[:-2]
        retained = others[-2:]

        to_compress_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in to_compress])
        prompt = f"Summarize the following conversation history densely in under 3 sentences:\n{to_compress_text}"

        import config
        import httpx
        import os

        fast_cfg = config.CAPABILITY_CATALOGUE.get("tier_1_fast", {})
        provider = fast_cfg.get("provider", "groq")
        model = fast_cfg.get("model", "llama-3.1-8b-instant")
        
        key_env = "GROQ_API_KEY" if provider == "groq" else "OPENROUTER_API_KEY"
        api_key = os.getenv(key_env, "")

        summary_text = ""
        url = "https://api.groq.com/openai/v1/chat/completions" if provider == "groq" else "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        json_data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=json_data, timeout=5.0)
                if response.status_code == 200:
                    res_json = response.json()
                    summary_text = res_json["choices"][0]["message"]["content"].strip()
                else:
                    logger.warning(f"Semantic compression: provider returned HTTP {response.status_code}.")
                    summary_text = f"[Context Compression]: Summarized {len(to_compress)} historical messages."
        except Exception as e:
            logger.error(f"Semantic history compression network failure: {e}")
            summary_text = f"[Context Compression]: Summarized {len(to_compress)} historical messages."

        summary_msg = {
            "role": "system",
            "content": f"[Semantic Summary Artifact]: {summary_text}",
            "pinned": True,
            "metadata": {"compressed_logs_count": len(to_compress)}
        }
        
        self._history = system + [summary_msg] + retained
        logger.info("Semantic compression completed.")
