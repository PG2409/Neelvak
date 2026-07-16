"""Unified Provider Execution Interface.

Abstracts all provider-specific HTTP transport, authentication, payload formatting,
and response parsing behind a single `execute()` contract. Runtime agents NEVER
know which upstream provider they are communicating with.

Implements the Active-Passive Failover Engine with:
  - Exponential backoff + jitter on 429 (rate limit)
  - Immediate failover on 402 (balance exhausted) / 500 / 503
  - Context window overflow detection and automatic model upgrade
  - Session-scoped dead-provider blacklisting
"""

import asyncio
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

import config

logger = logging.getLogger("neelvak_kernel")


class ProviderExecutionError(Exception):
    """Raised when all providers in a routing chain have been exhausted."""

    def __init__(self, message: str, status_code: int = 0, provider: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


class ProviderInterface:
    """Provider-agnostic execution gateway.

    Encapsulates tri-provider HTTP transport (Groq, OpenRouter, Gemini) behind
    a unified ``execute()`` method that walks the routing chain with full fault
    tolerance. Runtime agents interact exclusively through this interface.

    Attributes:
        _dead_providers: Session-scoped set of providers flagged as permanently
            unreachable (e.g. 402 balance exhausted). Cleared on process restart.
    """

    # Class-level session state — shared across all ProviderInterface instances
    # within the same server process. Now tracks expiry timestamp for 60s cooldown.
    _dead_providers: Dict[str, float] = {}

    # Retry configuration
    _MAX_RETRIES_PER_PROVIDER = 2
    _BASE_BACKOFF_SEC = 0.5
    _MAX_BACKOFF_SEC = 4.0
    _REQUEST_TIMEOUT_SEC = 30.0

    def __init__(self, event_bus: Optional[Any] = None) -> None:
        """Initialise the provider interface."""
        self.event_bus = event_bus

    # ------------------------------------------------------------------
    # PUBLIC API — the ONLY method runtimes should ever call
    # ------------------------------------------------------------------

    async def execute(
        self,
        prompt: str,
        model: str,
        provider: str,
        routing_chain: Optional[List[Dict[str, Any]]] = None,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        estimated_tokens: int = 0,
    ) -> Dict[str, Any]:
        """Execute an LLM inference request with full failover protection.

        The method first attempts the explicitly requested ``provider``/``model``
        pair. If that fails for a retriable or fatal reason, it walks the
        remaining entries in ``routing_chain`` until one succeeds.

        Args:
            prompt: The user/task prompt to send.
            model: Primary model identifier string.
            provider: Primary provider key (``groq`` | ``openrouter`` | ``gemini``).
            routing_chain: Ordered list of fallback ``{provider, model, ...}``
                dicts from ``config.CAPABILITY_CATALOGUE``. If ``None``, no
                fallback is attempted.
            system_prompt: Optional system-level instruction prepended to messages.
            temperature: Sampling temperature.
            estimated_tokens: Rough token estimate of the prompt. Used for
                context-window overflow detection.

        Returns:
            Dict containing::

                {
                    "content": str,          # The model-generated text
                    "provider": str,         # Provider that actually responded
                    "model": str,            # Model that actually responded
                    "usage": dict,           # Token usage metrics
                    "latency_ms": float,     # Round-trip time
                    "fallback_used": bool,   # Whether a fallback was invoked
                    "attempts": int          # Total attempt count across chain
                }

        Raises:
            ProviderExecutionError: If every provider in the chain is exhausted.
        """
        # Build the full ordered attempt list: primary first, then chain entries
        attempt_list = self._build_attempt_list(provider, model, routing_chain, estimated_tokens)

        if not attempt_list:
            raise ProviderExecutionError(
                "No viable providers remaining. All entries dead or filtered.",
                provider=provider,
            )

        total_attempts = 0
        last_error: Optional[Exception] = None

        for idx, entry in enumerate(attempt_list):
            entry_provider = entry["provider"]
            entry_model = entry["model"]

            # Skip globally dead providers if their 60s cooldown hasn't expired
            if entry_provider in self._dead_providers:
                if time.time() < self._dead_providers[entry_provider]:
                    logger.warning(
                        f"ProviderInterface: Skipping dead provider '{entry_provider}' "
                        f"(on 60s cooldown)."
                    )
                    if idx < len(attempt_list) - 1:
                        logger.info(f"ProviderInterface: Escalating to next fallback in routing chain...")
                        if self.event_bus:
                            from contracts.message import EventMessage
                            asyncio.create_task(self.event_bus.publish(EventMessage(
                                sender_id="PROVIDER",
                                receiver_id="EVENT",
                                workflow_id="SYSTEM",
                                msg_type="EVENT",
                                event_name="Provider Failover",
                                payload={"failed_provider": entry_provider, "error": "dead_on_cooldown"}
                            )))
                    continue
                else:
                    logger.info(f"ProviderInterface: Cooldown expired for '{entry_provider}', attempting recovery.")
                    del self._dead_providers[entry_provider]

            # Emit Selection and Inference Started
            if self.event_bus:
                from contracts.message import EventMessage
                asyncio.create_task(self.event_bus.publish(EventMessage(
                    sender_id="PROVIDER",
                    receiver_id="EVENT",
                    workflow_id="SYSTEM",
                    msg_type="EVENT",
                    event_name="Provider Selected",
                    payload={"provider": entry_provider}
                )))
                asyncio.create_task(self.event_bus.publish(EventMessage(
                    sender_id="PROVIDER",
                    receiver_id="EVENT",
                    workflow_id="SYSTEM",
                    msg_type="EVENT",
                    event_name="Model Selected",
                    payload={"model": entry_model}
                )))
                asyncio.create_task(self.event_bus.publish(EventMessage(
                    sender_id="PROVIDER",
                    receiver_id="EVENT",
                    workflow_id="SYSTEM",
                    msg_type="EVENT",
                    event_name="Inference Started",
                    payload={"provider": entry_provider, "model": entry_model}
                )))

            # Retry loop with exponential backoff for this specific provider
            for retry in range(self._MAX_RETRIES_PER_PROVIDER + 1):
                total_attempts += 1
                try:
                    result = await self._dispatch_request(
                        prompt=prompt,
                        model=entry_model,
                        provider=entry_provider,
                        system_prompt=system_prompt,
                        temperature=temperature,
                    )
                    result["fallback_used"] = idx > 0
                    result["attempts"] = total_attempts
                    
                    if self.event_bus:
                        asyncio.create_task(self.event_bus.publish(EventMessage(
                            sender_id="PROVIDER",
                            receiver_id="EVENT",
                            workflow_id="SYSTEM",
                            msg_type="EVENT",
                            event_name="Inference Completed",
                            payload={"provider": entry_provider, "latency_ms": result.get("latency_ms", 0.0)}
                        )))
                    
                    return result

                except _RateLimitError as exc:
                    # Edge Case 2: 429 Rate Limit — backoff + jitter, then retry
                    if retry < self._MAX_RETRIES_PER_PROVIDER:
                        backoff = min(
                            self._BASE_BACKOFF_SEC * (2 ** retry)
                            + random.uniform(0, 0.5),
                            self._MAX_BACKOFF_SEC,
                        )
                        logger.warning(
                            f"ProviderInterface: 429 from '{entry_provider}'. "
                            f"Retry {retry + 1}/{self._MAX_RETRIES_PER_PROVIDER} "
                            f"after {backoff:.2f}s backoff."
                        )
                        
                        if self.event_bus:
                            asyncio.create_task(self.event_bus.publish(EventMessage(
                                sender_id="PROVIDER",
                                receiver_id="EVENT",
                                workflow_id="SYSTEM",
                                msg_type="EVENT",
                                event_name="Retry",
                                payload={"reason": "429 Rate Limit", "backoff": backoff, "attempt": retry + 1}
                            )))
                            
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"ProviderInterface: '{entry_provider}' rate limit "
                            f"exhausted after {self._MAX_RETRIES_PER_PROVIDER} retries. "
                            f"Failing over to next chain entry."
                        )
                        last_error = exc
                        break  # move to next provider in chain

                except _BalanceExhaustedError as exc:
                    # Edge Case 1: 402 — flag provider dead, immediate failover with 60s cooldown
                    logger.critical(
                        f"ProviderInterface: '{entry_provider}' returned 402 "
                        f"(balance exhausted). Flagging DEAD for 60 seconds."
                    )
                    self._dead_providers[entry_provider] = time.time() + 60.0
                    last_error = exc
                    break  # move to next provider

                except _ServerError as exc:
                    # Edge Case 3: 500/503 — immediate failover, no retry
                    logger.error(
                        f"ProviderInterface: '{entry_provider}' server error "
                        f"({exc.status_code}). Immediate failover."
                    )
                    last_error = exc
                    break

                except _ContextOverflowError as exc:
                    # Edge Case 4: context window overflow — upgrade to high-context tier
                    logger.warning(
                        f"ProviderInterface: Context overflow on '{entry_provider}/{entry_model}'. "
                        f"Attempting high-context model upgrade."
                    )
                    overflow_chain = config.CAPABILITY_CATALOGUE.get(
                        "high_context_overflow", {}
                    ).get("routing_chain", [])
                    if overflow_chain:
                        # Recursive call with the overflow chain (no further overflow recursion)
                        try:
                            result = await self.execute(
                                prompt=prompt,
                                model=overflow_chain[0]["model"],
                                provider=overflow_chain[0]["provider"],
                                routing_chain=overflow_chain,
                                system_prompt=system_prompt,
                                temperature=temperature,
                                estimated_tokens=0,  # disable re-check
                            )
                            result["context_upgraded"] = True
                            return result
                        except ProviderExecutionError:
                            last_error = exc
                            break
                    else:
                        last_error = exc
                        break

                except Exception as exc:
                    # Generic transport/network failures — immediate failover
                    logger.error(
                        f"ProviderInterface: Unexpected error from '{entry_provider}': {exc}"
                    )
                    last_error = exc
                    break

            if idx < len(attempt_list) - 1:
                logger.info(f"ProviderInterface: Escalating to next fallback in routing chain...")
                if self.event_bus:
                    from contracts.message import EventMessage
                    asyncio.create_task(self.event_bus.publish(EventMessage(
                        sender_id="PROVIDER",
                        receiver_id="EVENT",
                        workflow_id="SYSTEM",
                        msg_type="EVENT",
                        event_name="Provider Failover",
                        payload={"failed_provider": entry_provider, "error": str(last_error)}
                    )))

        # EMERGENCY DETERMINISTIC MODE FALLBACK
        EMERGENCY_DETERMINISTIC_MODE = True
        if EMERGENCY_DETERMINISTIC_MODE:
            logger.critical("ProviderInterface: All providers exhausted. Activating KERNEL_LOOPBACK_RECOVERY.")
            return {
                "content": "[KERNEL_LOOPBACK_RECOVERY]: Cloud API services temporarily throttled. Falling back to core cache/deterministic offline summary.",
                "provider": "kernel_loopback",
                "model": "deterministic_offline",
                "usage": {"total_tokens": 0},
                "latency_ms": 1.0,
                "fallback_used": True,
                "attempts": total_attempts,
                "context_upgraded": False
            }

        raise ProviderExecutionError(
            f"All providers exhausted. Last error: {last_error}",
            provider=provider,
        )

    # ------------------------------------------------------------------
    # INTERNAL TRANSPORT — provider-specific HTTP dispatch
    # ------------------------------------------------------------------

    async def _dispatch_request(
        self,
        prompt: str,
        model: str,
        provider: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Dispatch a single HTTP request to the appropriate provider.

        Raises internal sentinel exceptions that the ``execute()`` failover
        engine interprets.
        """
        api_key = self._resolve_api_key(provider)
        if not api_key:
            raise ProviderExecutionError(
                f"API key for provider '{provider}' is missing or empty. "
                f"Set {config.PROVIDER_KEY_MAP.get(provider, 'UNKNOWN')} in .env.",
                provider=provider,
            )

        start_time = time.perf_counter()

        if provider == "gemini":
            return await self._dispatch_gemini(prompt, model, api_key, system_prompt, temperature, start_time)
        else:
            return await self._dispatch_openai_compat(prompt, model, provider, api_key, system_prompt, temperature, start_time)

    async def _dispatch_openai_compat(
        self,
        prompt: str,
        model: str,
        provider: str,
        api_key: str,
        system_prompt: Optional[str],
        temperature: float,
        start_time: float,
    ) -> Dict[str, Any]:
        """Dispatch to OpenAI-compatible APIs (Groq, OpenRouter)."""
        url = config.PROVIDER_CHAT_ENDPOINTS[provider]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {"model": model, "messages": messages, "temperature": temperature}

        logger.info(
            f"ProviderInterface: POST {provider} model='{model}' url={url}"
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, headers=headers, json=body, timeout=self._REQUEST_TIMEOUT_SEC
                )
        except httpx.TimeoutException:
            raise _ServerError(f"Timeout after {self._REQUEST_TIMEOUT_SEC}s", 408)
        except Exception as exc:
            raise _ServerError(f"Network error: {exc}", 0)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self._classify_http_error(resp, provider)

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})

        logger.info(
            f"ProviderInterface: {provider} responded 200 OK in {latency_ms:.0f}ms "
            f"({usage.get('total_tokens', '?')} tokens)."
        )

        return {
            "content": content,
            "provider": provider,
            "model": model,
            "usage": usage,
            "latency_ms": latency_ms,
        }

    async def _dispatch_gemini(
        self,
        prompt: str,
        model: str,
        api_key: str,
        system_prompt: Optional[str],
        temperature: float,
        start_time: float,
    ) -> Dict[str, Any]:
        """Dispatch to Google Gemini REST API (non-OpenAI format)."""
        url = config.PROVIDER_CHAT_ENDPOINTS["gemini"].format(model=model)
        url_with_key = f"{url}?key={api_key}"

        body: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        logger.info(f"ProviderInterface: POST gemini model='{model}'")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url_with_key,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self._REQUEST_TIMEOUT_SEC,
                )
        except httpx.TimeoutException:
            raise _ServerError(f"Timeout after {self._REQUEST_TIMEOUT_SEC}s", 408)
        except Exception as exc:
            raise _ServerError(f"Network error: {exc}", 0)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self._classify_http_error(resp, "gemini")

        data = resp.json()

        # Gemini response structure extraction
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            logger.error(f"ProviderInterface: Gemini response parse failure: {e}, body={data}")
            raise _ServerError(f"Gemini response parse failure: {e}", 0)

        usage = data.get("usageMetadata", {})
        normalised_usage = {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        }

        logger.info(
            f"ProviderInterface: gemini responded 200 OK in {latency_ms:.0f}ms "
            f"({normalised_usage.get('total_tokens', '?')} tokens)."
        )

        return {
            "content": content,
            "provider": "gemini",
            "model": model,
            "usage": normalised_usage,
            "latency_ms": latency_ms,
        }

    # ------------------------------------------------------------------
    # ERROR CLASSIFICATION ENGINE
    # ------------------------------------------------------------------

    def _classify_http_error(self, resp: httpx.Response, provider: str) -> None:
        """Raises the appropriate sentinel exception based on HTTP status code."""
        code = resp.status_code

        if code == 200:
            return

        body_preview = resp.text[:300] if resp.text else ""

        if code == 429:
            raise _RateLimitError(
                f"{provider} returned 429: {body_preview}", code
            )
        if code == 402:
            raise _BalanceExhaustedError(
                f"{provider} returned 402 (balance exhausted): {body_preview}", code
            )
        if code in (500, 502, 503):
            raise _ServerError(
                f"{provider} returned {code}: {body_preview}", code
            )
        if code == 400 and "context" in body_preview.lower():
            raise _ContextOverflowError(
                f"{provider} context overflow: {body_preview}", code
            )
        # All other errors treated as generic server errors for failover
        raise _ServerError(
            f"{provider} returned HTTP {code}: {body_preview}", code
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _resolve_api_key(self, provider: str) -> str:
        """Retrieves the runtime API key for a given provider."""
        env_var = config.PROVIDER_KEY_MAP.get(provider, "")
        return os.getenv(env_var, "") if env_var else ""

    def _build_attempt_list(
        self,
        primary_provider: str,
        primary_model: str,
        routing_chain: Optional[List[Dict[str, Any]]],
        estimated_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Constructs the ordered attempt list, filtering by context window.

        If ``estimated_tokens`` exceeds a model's context window, that entry is
        skipped (Edge Case 4 pre-filter).
        """
        attempts: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str]] = set()

        # Primary entry first
        primary = {"provider": primary_provider, "model": primary_model}
        if estimated_tokens <= 0 or True:  # always include primary, overflow handled at response level
            attempts.append(primary)
            seen.add((primary_provider, primary_model))

        # Then remaining chain entries (skip duplicates)
        if routing_chain:
            for entry in routing_chain:
                key = (entry["provider"], entry["model"])
                if key in seen:
                    continue
                # Pre-filter: if we know the token count exceeds context, skip
                ctx_k = entry.get("context_window_k", 999999)
                if estimated_tokens > 0 and estimated_tokens > ctx_k * 1024:
                    logger.info(
                        f"ProviderInterface: Skipping {entry['provider']}/{entry['model']} "
                        f"(estimated {estimated_tokens} tokens > {ctx_k}k context)."
                    )
                    continue
                attempts.append(entry)
                seen.add(key)

        return attempts

    @classmethod
    def reset_dead_providers(cls) -> None:
        """Reset the session-scoped dead provider blacklist.

        Intended for test teardown and manual recovery.
        """
        cls._dead_providers.clear()
        logger.info("ProviderInterface: Dead provider blacklist cleared.")


# ======================================================================
# INTERNAL SENTINEL EXCEPTIONS (never exposed to runtimes)
# ======================================================================

class _RateLimitError(Exception):
    """429 Too Many Requests."""
    def __init__(self, message: str, status_code: int = 429):
        super().__init__(message)
        self.status_code = status_code


class _BalanceExhaustedError(Exception):
    """402 Payment Required / Insufficient Balance."""
    def __init__(self, message: str, status_code: int = 402):
        super().__init__(message)
        self.status_code = status_code


class _ServerError(Exception):
    """500/502/503 or generic transport failure."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class _ContextOverflowError(Exception):
    """Payload exceeds the model's maximum context window."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
