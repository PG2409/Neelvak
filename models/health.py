"""Provider Health State Machine Daemon.

Heartbeats upstream endpoint probes to compile real-time provider status states.
"""

import asyncio
import logging
import httpx
import time
from enum import Enum
from typing import Dict, Optional
import config

logger = logging.getLogger("neelvak_kernel")

class ProviderState(str, Enum):
    """Rigid state parameters tracking network health of API providers."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERING = "RECOVERING"

class ProviderHealthManager:
    """Async background loop mapping health check probes to provider state matrices."""

    def __init__(self, heartbeat_interval_sec: float = 30.0) -> None:
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self._states: Dict[str, ProviderState] = {
            "groq": ProviderState.HEALTHY,
            "openrouter": ProviderState.HEALTHY,
            "gemini": ProviderState.HEALTHY
        }
        self._fail_counters: Dict[str, int] = {"groq": 0, "openrouter": 0, "gemini": 0}
        self._success_counters: Dict[str, int] = {"groq": 0, "openrouter": 0, "gemini": 0}
        self._state_timestamps: Dict[str, float] = {"groq": 0.0, "openrouter": 0.0, "gemini": 0.0}
        
        # Phase 2: Telemetry Metrics
        self._historical_latencies: Dict[str, List[float]] = {"groq": [], "openrouter": [], "gemini": []}
        self._quotas: Dict[str, float] = {"groq": 1000.0, "openrouter": 1000.0, "gemini": 1000.0}
        self._queue_depths: Dict[str, int] = {"groq": 0, "openrouter": 0, "gemini": 0}
        self._total_requests: Dict[str, int] = {"groq": 0, "openrouter": 0, "gemini": 0}
        self._successful_requests: Dict[str, int] = {"groq": 0, "openrouter": 0, "gemini": 0}
        
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Launches the health monitoring daemon."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("ProviderHealthManager daemon started.")

    async def stop(self) -> None:
        """Terminates the health monitoring daemon."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ProviderHealthManager daemon stopped.")

    def get_status(self, provider: str) -> ProviderState:
        """Returns the current tracked health state of a provider with 60s auto-expiry."""
        current = self._states.get(provider, ProviderState.OFFLINE)
        
        # Auto-expire non-healthy statuses after 60 seconds cooldown
        if current in [ProviderState.DEGRADED, ProviderState.OFFLINE]:
            last_failed = self._state_timestamps.get(provider, 0.0)
            if time.time() - last_failed > 60.0:
                logger.info(f"ProviderHealthManager: {provider} degraded state expired after 60s. Auto-reverting to HEALTHY.")
                self._states[provider] = ProviderState.HEALTHY
                self._fail_counters[provider] = 0
                return ProviderState.HEALTHY
                
        return current
        
    def set_status_for_testing(self, provider: str, state: ProviderState) -> None:
        """Helper strictly for unit testing state transitions."""
        self._states[provider] = state
        if state == ProviderState.HEALTHY:
            self._fail_counters[provider] = 0
            self._success_counters[provider] = 0

    def get_historical_latency(self, provider: str) -> float:
        lats = self._historical_latencies.get(provider, [])
        return sum(lats) / len(lats) if lats else 500.0

    def get_success_rate(self, provider: str) -> float:
        tot = self._total_requests.get(provider, 0)
        suc = self._successful_requests.get(provider, 0)
        return (suc / tot) if tot > 0 else 1.0

    def get_quota(self, provider: str) -> float:
        return self._quotas.get(provider, 1000.0)

    def get_queue_depth(self, provider: str) -> int:
        return self._queue_depths.get(provider, 0)

    def record_request_latency(self, provider: str, latency_ms: float) -> None:
        if provider not in self._historical_latencies:
            self._historical_latencies[provider] = []
        lats = self._historical_latencies[provider]
        lats.append(latency_ms)
        if len(lats) > 100:
            lats.pop(0)

    def increment_queue(self, provider: str) -> None:
        if provider in self._queue_depths:
            self._queue_depths[provider] += 1

    def decrement_queue(self, provider: str) -> None:
        if provider in self._queue_depths and self._queue_depths[provider] > 0:
            self._queue_depths[provider] -= 1

    async def _monitor_loop(self) -> None:
        """Asynchronous execution loop probing providers in background."""
        while self._running:
            for provider, url in config.PROVIDER_PROBES.items():
                await self._probe_provider(provider, url)
            await asyncio.sleep(self.heartbeat_interval_sec)

    async def _probe_provider(self, provider: str, url: str) -> None:
        """Sends a GET/POST probe to verify provider responsiveness."""
        current_state = self._states[provider]
        try:
            # We use a short 3.0s timeout to detect latency/flapping early
            import os
            key_env = config.PROVIDER_KEY_MAP.get(provider, "")
            api_key = os.getenv(key_env, "") if key_env else ""
            async with httpx.AsyncClient() as client:
                if provider == "gemini":
                    # Gemini uses API key as query parameter, not Bearer token
                    probe_url = f"{url}?key={api_key}" if api_key else url
                    response = await client.get(probe_url, timeout=3.0)
                else:
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    response = await client.get(url, headers=headers, timeout=3.0)
                success = (response.status_code == 200)

            if success:
                self.record_success(provider)
            else:
                logger.warning(
                    f"ProviderHealthManager: {provider} health probe returned HTTP {response.status_code}. "
                    f"Check that {key_env} is set to a valid API key."
                )
                self.record_failure(provider)
        except Exception as e:
            logger.warning(f"Connection exception checking health of {provider}: {e}")
            self.record_failure(provider)

    def record_success(self, provider: str, is_probe: bool = True) -> None:
        """Records a successful network ping and handles state escalations."""
        current_state = self._states[provider]
        self._fail_counters[provider] = 0
        if is_probe:
            self._success_counters[provider] += 1
            
        self._total_requests[provider] = self._total_requests.get(provider, 0) + 1
        self._successful_requests[provider] = self._successful_requests.get(provider, 0) + 1
        
        if current_state == ProviderState.OFFLINE:
            self._states[provider] = ProviderState.RECOVERING
            self._success_counters[provider] = 1
            logger.info(f"Provider {provider} recovering from outage.")
        elif current_state == ProviderState.RECOVERING:
            if self._success_counters[provider] >= 3:
                self._states[provider] = ProviderState.HEALTHY
                logger.info(f"Provider {provider} restored to HEALTHY state.")
        elif current_state == ProviderState.DEGRADED:
            self._states[provider] = ProviderState.HEALTHY
            logger.info(f"Provider {provider} upgraded to HEALTHY state.")
            
    def record_failure(self, provider: str, is_probe: bool = True) -> None:
        """Records a network failure and handles state escalations."""
        if is_probe:
            self._fail_counters[provider] += 1
            self._success_counters[provider] = 0
            
        self._total_requests[provider] = self._total_requests.get(provider, 0) + 1
            
        fails = self._fail_counters[provider]
        current_state = self._states[provider]

        if current_state == ProviderState.HEALTHY or current_state == ProviderState.RECOVERING:
            if fails >= 1:
                self._states[provider] = ProviderState.DEGRADED
                self._state_timestamps[provider] = time.time()
                logger.warning(f"Provider {provider} state degraded due to failure.")
                
        if fails >= 3 and current_state != ProviderState.OFFLINE:
            self._states[provider] = ProviderState.OFFLINE
            self._state_timestamps[provider] = time.time()
            logger.critical(f"Provider {provider} offline! Maximum check failures reached.")
