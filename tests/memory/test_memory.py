"""Unit tests for Phase 4 Caching Subsystems.

Verifies adaptive CSS thresholds, L3-to-L1 cache promotion logic,
and context manager sliding window truncation.
"""

import os
import sys
import asyncio
import unittest
import pytest

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory.manager import MemoryManager, CacheDeficiencyException
from memory.context import ContextManager

class TestMemoryCachingAndContext(unittest.IsolatedAsyncioTestCase):
    """Test suite validating Phase 4 Memory features."""

    def test_adaptive_css_thresholds(self):
        """Verifies that CSS threshold gates differentiate hits/misses by runtime."""
        manager = MemoryManager()
        
        # We query with prompt: "compile intent plan"
        # Let's verify CSS calculations
        prompt = "compile intent plan"
        
        # Test search under DIRECT (threshold 0.55) -> must HIT
        hit_direct, val_direct, css_direct = manager.check_cache_hit(prompt, "DIRECT")
        self.assertTrue(hit_direct)
        self.assertIsNotNone(val_direct)
        
        # Test search under COMPETITIVE (threshold 0.95) -> must MISS
        hit_comp, val_comp, css_comp = manager.check_cache_hit(prompt, "COMPETITIVE")
        self.assertFalse(hit_comp)
        self.assertIsNone(val_comp)

    def test_cache_promotion_integrity(self):
        """Verifies that repeating lookups on long-term keywords promotes them to L1."""
        manager = MemoryManager()
        keyword = "security policy"
        
        # Initially, keyword is not present in L1 cache
        self.assertNotIn(keyword, manager._l1_cache)
        
        # Retrieve keyword 3 times (frequency ceiling is 3) using DIRECT runtime (threshold 0.55)
        for _ in range(3):
            hit, val, css = manager.check_cache_hit(keyword, "DIRECT")
            self.assertTrue(hit)
            
        # The 3rd hit must trigger promotion to L1 cache
        self.assertIn(keyword, manager._l1_cache)
        self.assertEqual(manager._l1_cache[keyword], "Trigger PolicyEngine validation rings to block cost or prompt anomalies.")

    def test_context_sliding_window_truncation(self):
        """Verifies context truncation drops oldest intermediates while preserving system/pinned/immediate query."""
        # max_tokens = 20 (which is 80 characters under 1 token ≈ 4 chars estimate)
        ctx = ContextManager(max_tokens=20)
        
        # Add system prompt (length 25 chars -> ~6 tokens)
        ctx.add_message("system", "SYSTEM_INSTRUCTION_LINE")
        
        # Add pinned instruction (length 20 chars -> ~5 tokens)
        ctx.add_message("user", "PINNED_PROMPT_RULE", pinned=True)
        
        # Add old intermediate messages (length 32 chars each -> ~8 tokens each)
        ctx.add_message("assistant", "OLD_MESSAGE_LOG_A")
        ctx.add_message("user", "OLD_MESSAGE_LOG_B")
        
        # Add immediate query (length 28 chars -> ~7 tokens)
        ctx.add_message("user", "IMMEDIATE_USER_QUERY_NOW")
        
        # Total required if everything preserved:
        # system (6) + pinned (5) + log A (8) + log B (8) + query (7) = 34 tokens.
        # This exceeds the max_tokens limit of 30!
        # Under sliding window logic, older intermediates must be dropped.
        # So "OLD_MESSAGE_LOG_A" should be dropped first.
        
        packed = ctx.pack_context()
        contents = [m["content"] for m in packed]
        
        # Assertions:
        # Pinned instructions, system parameters, and immediate queries must be retained.
        self.assertIn("SYSTEM_INSTRUCTION_LINE", contents)
        self.assertIn("PINNED_PROMPT_RULE", contents)
        self.assertIn("IMMEDIATE_USER_QUERY_NOW", contents)
        
        # Oldest intermediate "OLD_MESSAGE_LOG_A" must be dropped
        self.assertNotIn("OLD_MESSAGE_LOG_A", contents)

    async def test_async_data_store_and_semantic_compression(self):
        """Verifies loading store asynchronously and executing semantic summary pipelines."""
        manager = MemoryManager()
        await manager.load_data_store_async()
        self.assertTrue(os.path.exists("data_store.json"))

        ctx = ContextManager(max_tokens=50)
        ctx.add_message("system", "SYSTEM_INSTRUCTIONS")
        ctx.add_message("user", "A")
        ctx.add_message("assistant", "B")
        ctx.add_message("user", "C")
        ctx.add_message("assistant", "D")
        ctx.add_message("user", "E")

        # Trigger compression pass with optimize=True to mock groq call
        await ctx.compress_history_semantic(optimize=True)
        
        contents = [m["content"] for m in ctx._history]
        self.assertTrue(any("Summary" in c for c in contents))

if __name__ == "__main__":
    unittest.main()
