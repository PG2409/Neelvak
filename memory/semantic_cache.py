"""Semantic Cache Layer for the Neelvak AIOS Context Engine.

Provides organization-scoped semantic similarity matching to prevent redundant
model calls. Uses normalized text fingerprinting with Jaccard similarity for
embedding-free operation (zero external dependencies).

Cache entries are TTL-bound and scoped per organization so that Employee A's
cached answer benefits Employee B in the same org without leaking across orgs.
"""

import time
import re
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

logger = logging.getLogger("neelvak_kernel")


@dataclass
class CacheEntry:
    """A single cached prompt-response pair with metadata."""
    prompt_normalized: str
    prompt_tokens: set
    response: str
    org_id: str
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class SemanticCache:
    """Organization-scoped semantic similarity cache with TTL expiration.
    
    This cache operates WITHOUT embeddings or external ML models. It uses
    normalized text tokenization + Jaccard similarity to detect semantically
    similar prompts. This is intentionally lightweight — the goal is to catch
    the 80% of cache-worthy queries (exact or near-exact repeats) at zero cost.
    
    For true deep semantic matching (paraphrase detection), a future upgrade
    would integrate sentence-transformer embeddings.
    """

    def __init__(self, ttl_seconds: int = 7200, similarity_threshold: float = 0.75) -> None:
        """Initialize the semantic cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 2 hours).
            similarity_threshold: Minimum Jaccard similarity to consider a cache hit.
        """
        self._entries: List[CacheEntry] = []
        self._ttl = ttl_seconds
        self._threshold = similarity_threshold
        
        # Analytics counters
        self.total_queries = 0
        self.total_hits = 0
        self.total_tokens_saved = 0

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def _tokenize(text: str) -> set:
        """Split normalized text into a set of unique word tokens."""
        return set(text.split()) if text else set()

    @staticmethod
    def _jaccard(set_a: set, set_b: set) -> float:
        """Compute Jaccard similarity between two token sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    def _evict_expired(self) -> None:
        """Remove entries that have exceeded their TTL."""
        now = time.time()
        before = len(self._entries)
        self._entries = [e for e in self._entries if (now - e.created_at) < self._ttl]
        evicted = before - len(self._entries)
        if evicted > 0:
            logger.debug(f"SemanticCache: Evicted {evicted} expired entries.")

    def query(self, prompt: str, org_id: str = "global") -> Tuple[bool, Optional[str], float]:
        """Check if a semantically similar prompt exists in the cache.
        
        Args:
            prompt: The raw user prompt string.
            org_id: Organization ID for scope isolation.
        
        Returns:
            Tuple of (is_hit, cached_response_or_None, similarity_score).
        """
        self.total_queries += 1
        self._evict_expired()

        normalized = self._normalize(prompt)
        tokens = self._tokenize(normalized)

        if not tokens:
            return False, None, 0.0

        best_score = 0.0
        best_entry: Optional[CacheEntry] = None

        for entry in self._entries:
            # Only match within the same organization
            if entry.org_id != org_id and entry.org_id != "global":
                continue
            
            score = self._jaccard(tokens, entry.prompt_tokens)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self._threshold and best_entry is not None:
            best_entry.hit_count += 1
            best_entry.last_accessed = time.time()
            self.total_hits += 1
            # Estimate tokens saved (rough: 4 chars per token)
            self.total_tokens_saved += max(len(best_entry.response) // 4, 1)
            logger.info(f"SemanticCache HIT (score={best_score:.2f}, org={org_id}): '{prompt[:50]}...'")
            return True, best_entry.response, best_score

        return False, None, best_score

    def store(self, prompt: str, response: str, org_id: str = "global") -> None:
        """Store a prompt-response pair in the cache.
        
        Args:
            prompt: The raw user prompt.
            response: The model's response.
            org_id: Organization ID for scope isolation.
        """
        normalized = self._normalize(prompt)
        tokens = self._tokenize(normalized)

        if not tokens or not response:
            return

        # Avoid storing duplicates
        for entry in self._entries:
            if entry.org_id == org_id:
                score = self._jaccard(tokens, entry.prompt_tokens)
                if score >= self._threshold:
                    # Update existing entry with newer response
                    entry.response = response
                    entry.created_at = time.time()
                    return

        self._entries.append(CacheEntry(
            prompt_normalized=normalized,
            prompt_tokens=tokens,
            response=response,
            org_id=org_id
        ))
        logger.info(f"SemanticCache STORED (org={org_id}): '{prompt[:50]}...'")

    def get_stats(self) -> dict:
        """Return cache performance analytics."""
        self._evict_expired()
        hit_rate = (self.total_hits / max(self.total_queries, 1)) * 100
        return {
            "total_queries": self.total_queries,
            "total_hits": self.total_hits,
            "hit_rate_pct": round(hit_rate, 1),
            "active_entries": len(self._entries),
            "estimated_tokens_saved": self.total_tokens_saved
        }
