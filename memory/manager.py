"""Multi-Tier Cache Controller & Promotion Engine.

Coordinates progressive memory tiers L1-L5, CSS gating metrics, and promotion policies.
"""

import logging
import os
import json
import aiofiles
from typing import Dict, Any, Optional, Tuple, Set, Union

logger = logging.getLogger("neelvak_kernel")

class CacheDeficiencyException(Exception):
    """Custom exception raised when internal memory tiers yield a deficiency exception."""
    pass

class MemoryManager:
    """Coordinates nested memory cache rings and computes Context Sufficiency Scores."""

    def __init__(self, cache_dir: str = "workspace/memory_cache", event_bus: Optional[Any] = None) -> None:
        self.cache_dir = cache_dir
        self.event_bus = event_bus
        os.makedirs(cache_dir, exist_ok=True)
        
        # L1: In-Memory Active Scope
        self._l1_cache: Dict[str, str] = {}
        self._l1_stats: Dict[str, int] = {}  # Tracks access counts for promotion
        
        # L2: Local Disk Session Store
        self._l2_metadata_path = os.path.join(cache_dir, "l2_manifest.json")
        self._load_l2_manifest()

        # L3: Cross-Session Long-Term Semantic Index (Keyword Index)
        self._l3_index: Dict[str, str] = {
            "initialize environment": "Execute EnvironmentFactory to allocate workspace caches.",
            "compile intent": "Deploy 10-Pass AICompiler to generate IR_v4 workflow plan structures.",
            "security policy": "Trigger PolicyEngine validation rings to block cost or prompt anomalies."
        }
        self._l3_stats: Dict[str, int] = {}

        # L4: Vector Database Stub Connector
        self._l4_vector_db: Dict[str, str] = {
            "sandbox configuration": "Configure directory sandboxing via factories and tool manager hooks."
        }
        self._l4_stats: Dict[str, int] = {}

        # L5: Live Web Indexing search hooks
        self._l5_search_index: Dict[str, str] = {
            "external dependencies": "Fetches standard packages and configurations from external repos."
        }
        self._l5_stats: Dict[str, int] = {}

    def _load_l2_manifest(self) -> None:
        if os.path.exists(self._l2_metadata_path):
            try:
                with open(self._l2_metadata_path, "r", encoding="utf-8") as f:
                    self._l2_manifest = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read L2 manifest: {e}")
                self._l2_manifest = {}
        else:
            self._l2_manifest = {}

    def _save_l2_manifest(self) -> None:
        try:
            with open(self._l2_metadata_path, "w", encoding="utf-8") as f:
                json.dump(self._l2_manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save L2 manifest: {e}")

    async def load_data_store_async(self) -> None:
        """Asynchronously reads data_store.json via aiofiles."""
        data_store_path = "data_store.json"
        try:
            if os.path.exists(data_store_path):
                async with aiofiles.open(data_store_path, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
                    logger.info(f"Asynchronously loaded data_store.json records successfully. Status: {data.get('status')}")
            else:
                # Initialize default file
                async with aiofiles.open(data_store_path, mode="w", encoding="utf-8") as f:
                    await f.write(json.dumps({"status": "healthy", "records": []}))
                logger.info("Initialized default data_store.json file.")
        except Exception as e:
            logger.error(f"Failed to asynchronously load/write data_store.json: {e}")

    def _calculate_css(self, prompt: str, context_block: Union[str, list]) -> float:
        """Calculates token overlap Sufficiency Score between prompt and context.

        Uses pure Jaccard similarity — symmetric over the token union, preventing
        short prompts from falsely matching long cached keys due to the subset effect.
        """
        if not prompt:
            return 0.0

        def tokenize(text: str) -> Set[str]:
            return set(text.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "").split())

        prompt_tokens = tokenize(prompt)

        if isinstance(context_block, list):
            context_tokens = set()
            for block in context_block:
                context_tokens.update(tokenize(str(block)))
        else:
            context_tokens = tokenize(str(context_block))

        if not prompt_tokens or not context_tokens:
            return 0.0

        intersection = prompt_tokens.intersection(context_tokens)
        union = prompt_tokens.union(context_tokens)

        # Pure Jaccard: symmetric, cannot be gamed by subset prompts.
        # A short prompt like "Hello" will only score high against a cached key
        # that is also very short and highly overlapping — not against a long paragraph.
        jaccard = len(intersection) / len(union) if union else 0.0
        return jaccard

    def check_cache_hit(self, prompt: str, runtime: str) -> Tuple[bool, Optional[str], float]:
        """Runs progressive cache pipeline and checks hit sufficiency by runtime type.

        Args:
            prompt: User-space query intent.
            runtime: Target runtime engine type.

        Returns:
            Tuple: (is_hit, matched_content, css_score)
        """
        thresholds = {
            "COMPETITIVE": 0.95,
            "STANDARD": 0.85,
            "MICRO": 0.70,
            "DIRECT": 0.55,
            "RETRIEVAL": 0.80
        }
        min_threshold = thresholds.get(runtime, 0.80)

        import asyncio
        start_time = asyncio.get_event_loop().time()
        
        if self.event_bus:
            from contracts.message import EventMessage
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="MEMORY_MANAGER",
                receiver_id="EVENT",
                workflow_id="GLOBAL",
                msg_type="EVENT",
                event_name="Cache Query",
                payload={"prompt": prompt[:50], "required_css": min_threshold, "runtime": runtime}
            )))

        # 1. Search L1 (Active Frame in RAM)
        for k, v in self._l1_cache.items():
            css = self._calculate_css(prompt, k)
            if css >= min_threshold:
                self._l1_stats[k] = self._l1_stats.get(k, 0) + 1
                latency = (asyncio.get_event_loop().time() - start_time) * 1000.0
                if self.event_bus:
                    asyncio.create_task(self.event_bus.publish(EventMessage(
                        sender_id="MEMORY_MANAGER",
                        receiver_id="EVENT",
                        workflow_id="GLOBAL",
                        msg_type="EVENT",
                        event_name="Memory Hit",
                        payload={
                            "Cache Layer": "L1", "Similarity": css, "Memory Source": "RAM",
                            "Document IDs": [hash(k)], "Access Count": self._l1_stats[k], "Latency": latency, "Context Sufficiency": True
                        }
                    )))
                logger.info(f"[L1 Hit] CSS {css:.2f} >= {min_threshold} threshold. short-circuiting.")
                return True, v, css

        # 2. Search L2 (Disk Session Store)
        for k, entry in self._l2_manifest.items():
            css = self._calculate_css(prompt, k)
            if css >= min_threshold:
                entry["access_count"] = entry.get("access_count", 0) + 1
                self._save_l2_manifest()
                
                content = self._read_l2_file(entry["path"])
                if content:
                    if entry["access_count"] >= 3:
                        # Promote to L1
                        self._l1_cache[k] = content
                        self._l1_stats[k] = 1
                        if self.event_bus:
                            asyncio.create_task(self.event_bus.publish(EventMessage(
                                sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                                event_name="Promotion", payload={"Source Layer": "L2", "Target Layer": "L1", "Document ID": hash(k), "Promotion Count": 1}
                            )))
                        logger.info(f"[L2 Promotion] Promoted context to L1 cache: '{k}'")
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000.0
                    if self.event_bus:
                        asyncio.create_task(self.event_bus.publish(EventMessage(
                            sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                            event_name="Memory Hit", payload={
                                "Cache Layer": "L2", "Similarity": css, "Memory Source": "Disk",
                                "Document IDs": [hash(k)], "Access Count": entry["access_count"], "Latency": latency, "Context Sufficiency": True
                            }
                        )))
                    logger.info(f"[L2 Hit] CSS {css:.2f} >= {min_threshold} threshold. short-circuiting.")
                    return True, content, css

        # 3. Search L3 (Cross-Session Keyword Index)
        for keyword, content in self._l3_index.items():
            css = self._calculate_css(prompt, keyword)
            if css >= min_threshold:
                self._l3_stats[keyword] = self._l3_stats.get(keyword, 0) + 1
                if self._l3_stats[keyword] >= 3:
                    # Promote to L1 / L2
                    self._l1_cache[keyword] = content
                    self._l1_stats[keyword] = 1
                    self.store_cache(keyword, content, scope="L2")
                    if self.event_bus:
                        asyncio.create_task(self.event_bus.publish(EventMessage(
                            sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                            event_name="Promotion", payload={"Source Layer": "L3", "Target Layer": "L1/L2", "Document ID": hash(keyword), "Promotion Count": 1}
                        )))
                    logger.info(f"[L3 Promotion] Promoted L3 keyword index to L1/L2: '{keyword}'")
                latency = (asyncio.get_event_loop().time() - start_time) * 1000.0
                if self.event_bus:
                    asyncio.create_task(self.event_bus.publish(EventMessage(
                        sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                        event_name="Memory Hit", payload={
                            "Cache Layer": "L3", "Similarity": css, "Memory Source": "Keyword Index",
                            "Document IDs": [hash(keyword)], "Access Count": self._l3_stats[keyword], "Latency": latency, "Context Sufficiency": True
                        }
                    )))
                logger.info(f"[L3 Hit] CSS {css:.2f} >= {min_threshold} threshold. short-circuiting.")
                return True, content, css

        # 4. Search L4 (Vector DB Connector Stub)
        for doc_key, content in self._l4_vector_db.items():
            css = self._calculate_css(prompt, doc_key)
            if css >= min_threshold:
                self._l4_stats[doc_key] = self._l4_stats.get(doc_key, 0) + 1
                logger.info(f"[L4 Hit] Vector connector match for: '{doc_key}' (CSS: {css:.2f})")
                if self._l4_stats[doc_key] >= 3:
                    self._l1_cache[doc_key] = content
                    self._l1_stats[doc_key] = 1
                    self.store_cache(doc_key, content, scope="L2")
                    if self.event_bus:
                        asyncio.create_task(self.event_bus.publish(EventMessage(
                            sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                            event_name="Promotion", payload={"Source Layer": "L4", "Target Layer": "L1/L2", "Document ID": hash(doc_key), "Promotion Count": 1}
                        )))
                    logger.info(f"[L4 Promotion] Promoted L4 vector stub to L1/L2: '{doc_key}'")
                latency = (asyncio.get_event_loop().time() - start_time) * 1000.0
                if self.event_bus:
                    asyncio.create_task(self.event_bus.publish(EventMessage(
                        sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                        event_name="Memory Hit", payload={
                            "Cache Layer": "L4", "Similarity": css, "Memory Source": "Vector DB Stub",
                            "Document IDs": [hash(doc_key)], "Access Count": self._l4_stats[doc_key], "Latency": latency, "Context Sufficiency": True
                        }
                    )))
                return True, content, css

        # 5. Search L5 (External Web Index Search Stub)
        for search_key, content in self._l5_search_index.items():
            css = self._calculate_css(prompt, search_key)
            if css >= min_threshold:
                self._l5_stats[search_key] = self._l5_stats.get(search_key, 0) + 1
                logger.info(f"[L5 Hit] External web indexing hit for: '{search_key}' (CSS: {css:.2f})")
                if self._l5_stats[search_key] >= 3:
                    self._l1_cache[search_key] = content
                    self._l1_stats[search_key] = 1
                    self.store_cache(search_key, content, scope="L2")
                    if self.event_bus:
                        asyncio.create_task(self.event_bus.publish(EventMessage(
                            sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                            event_name="Promotion", payload={"Source Layer": "L5", "Target Layer": "L1/L2", "Document ID": hash(search_key), "Promotion Count": 1}
                        )))
                    logger.info(f"[L5 Promotion] Promoted L5 web index search stub to L1/L2: '{search_key}'")
                latency = (asyncio.get_event_loop().time() - start_time) * 1000.0
                if self.event_bus:
                    asyncio.create_task(self.event_bus.publish(EventMessage(
                        sender_id="MEMORY_MANAGER", receiver_id="EVENT", workflow_id="GLOBAL", msg_type="EVENT",
                        event_name="Memory Hit", payload={
                            "Cache Layer": "L5", "Similarity": css, "Memory Source": "Web Index",
                            "Document IDs": [hash(search_key)], "Access Count": self._l5_stats[search_key], "Latency": latency, "Context Sufficiency": True
                        }
                    )))
                return True, content, css

        # Failure: Raise deficiency exception warning logs
        logger.warning(f"Cache miss across L1-L5 memory tiers for prompt: '{prompt}' (Required: {min_threshold})")
        return False, None, 0.0

    def _read_l2_file(self, filepath: str) -> Optional[str]:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"L2 Cache read file failure: {e}")
        return None

    def store_cache(self, prompt: str, content: str, scope: str = "L2") -> None:
        """Saves output to memory tiers.

        Args:
            prompt: Query key.
            content: Result to cache.
            scope: Target tier.
        """
        if scope == "L1":
            self._l1_cache[prompt] = content
            self._l1_stats[prompt] = 0
            logger.info("Stored output in L1 in-memory cache.")
        else:
            # Write to L2 disk file
            filename = f"l2_{hash(prompt)}.txt"
            filepath = os.path.join(self.cache_dir, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                self._l2_manifest[prompt] = {
                    "path": filepath,
                    "access_count": 0
                }
                self._save_l2_manifest()
                logger.info(f"Stored output in L2 disk cache at {filepath}")
            except Exception as e:
                logger.error(f"L2 disk caching store failure: {e}")
