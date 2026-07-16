"""Multi-Tenant Authentication Data Models.

Manages Organizations, Employees, and role-based access for the Neelvak AIOS platform.
"""

import uuid
import time
import hashlib
import secrets
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


class Employee(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    name: str
    email: str
    role: Role = Role.MEMBER
    password_hash: str = ""
    monthly_budget_usd: float = 200.0
    tokens_used_this_month: int = 0
    total_requests: int = 0
    created_at: float = Field(default_factory=time.time)


class Organization(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    admin_employee_id: str = ""
    monthly_budget_usd: float = 5000.0
    total_tokens_used: int = 0
    created_at: float = Field(default_factory=time.time)


def hash_password(password: str) -> str:
    """Create a salted SHA-256 hash of a password string."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salted hash."""
    try:
        salt, hashed = stored_hash.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except (ValueError, AttributeError):
        return False


# In-memory stores (production would use PostgreSQL/SQLite)
organizations: Dict[str, Organization] = {}
employees: Dict[str, Employee] = {}
email_index: Dict[str, str] = {}  # email -> employee_id
