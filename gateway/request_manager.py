"""Session Validation and Rate Limiting.

Limits intent gateway calls to prevent concurrent rate bottlenecks.
"""

import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger("neelvak_kernel")

class RequestManager:
    """Enforces rate limiting limits and checks incoming session IDs."""

    def __init__(self, max_requests_per_min: int = 15) -> None:
        import os
        env_limit = os.environ.get("AIOS_MAX_REQUESTS_PER_MIN")
        self.max_requests_per_min = int(env_limit) if env_limit else max_requests_per_min
        # Map user/IP sessions to list of timestamps
        self._rate_limits: Dict[str, List[float]] = {}

    def validate_request(self, payload: dict, session_id: str) -> Tuple[bool, str, dict]:
        """Validates current session call budgets and rate limits.

        Args:
            payload: Raw inbound gateway dictionary inputs.
            session_id: Client identifier string.

        Returns:
            Tuple (is_allowed, details, sanitized_payload)
        """
        logger.info(f"RequestManager: Auditing gateway call for session: {session_id}")
        
        now = time.time()
        
        # Initialize limit arrays
        if session_id not in self._rate_limits:
            self._rate_limits[session_id] = []
            
        timestamps = self._rate_limits[session_id]
        
        # Evict timestamps older than 60 seconds
        self._rate_limits[session_id] = [t for t in timestamps if now - t < 60.0]
        
        # Strip dirty or unauthorized injection values
        sanitized_payload = {}
        if isinstance(payload, dict):
            allowed_keys = {"prompt", "options"}
            sanitized_payload = {k: v for k, v in payload.items() if k in allowed_keys}
            # ensure prompt is a string
            if "prompt" in sanitized_payload and not isinstance(sanitized_payload["prompt"], str):
                sanitized_payload["prompt"] = str(sanitized_payload["prompt"])
        else:
            return False, "Invalid Payload Structure", {}

        if len(self._rate_limits[session_id]) >= self.max_requests_per_min:
            logger.warning(f"RequestManager: Session '{session_id}' exceeded rate limit thresholds.")
            return False, "Rate Limit Exceeded: Maximum 15 requests per minute allowed.", sanitized_payload
            
        self._rate_limits[session_id].append(now)
        logger.info(f"RequestManager: Session audit verified. Requests count in last minute: {len(self._rate_limits[session_id])}")
        return True, "OK", sanitized_payload
