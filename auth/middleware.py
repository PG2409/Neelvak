"""JWT Authentication Middleware for FastAPI.

Provides HMAC-based token generation, validation, and FastAPI dependency injection.
No external JWT library required — uses Python stdlib only.
"""

import json
import time
import hmac
import hashlib
import base64
import logging
from typing import Optional
from fastapi import Request, HTTPException

logger = logging.getLogger("neelvak_kernel")

JWT_SECRET = "neelvak-aios-v1.3-secret-key-change-in-production"
TOKEN_EXPIRY_HOURS = 24


def create_token(employee_id: str, org_id: str, role: str) -> str:
    """Generate a signed authentication token.
    
    Args:
        employee_id: Unique employee identifier.
        org_id: Organization identifier.
        role: Employee role (admin/member).
    
    Returns:
        A base64-encoded payload with HMAC signature.
    """
    payload = {
        "employee_id": employee_id,
        "org_id": org_id,
        "role": role,
        "exp": time.time() + (TOKEN_EXPIRY_HOURS * 3600)
    }
    payload_bytes = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(JWT_SECRET.encode(), payload_bytes.encode(), hashlib.sha256).hexdigest()
    return f"{payload_bytes}.{signature}"


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a signed authentication token.
    
    Args:
        token: The full token string (payload.signature).
    
    Returns:
        The decoded payload dict, or None if invalid/expired.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_bytes, signature = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), payload_bytes.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_bytes.encode()).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


async def get_current_employee(request: Request) -> dict:
    """FastAPI dependency: Extract and validate auth token from request headers.
    
    Usage:
        @router.get("/protected")
        async def protected_route(current=Depends(get_current_employee)):
            return {"employee_id": current["employee_id"]}
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
