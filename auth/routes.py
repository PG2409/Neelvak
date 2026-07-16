"""Authentication API Routes.

Handles organization registration, employee login, team invites, budget controls,
and per-employee usage analytics for the Neelvak AIOS multi-tenant platform.
"""

import logging
import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth.models import (
    Organization, Employee, Role,
    organizations, employees, email_index,
    hash_password, verify_password
)
from auth.middleware import create_token, get_current_employee

logger = logging.getLogger("neelvak_kernel")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# =====================================================================
# REQUEST SCHEMAS
# =====================================================================

class RegisterRequest(BaseModel):
    org_name: str
    admin_name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class InviteRequest(BaseModel):
    name: str
    email: str
    role: str = "member"
    monthly_budget_usd: float = 200.0

class SetBudgetRequest(BaseModel):
    employee_id: str
    monthly_budget_usd: float


# =====================================================================
# ROUTES
# =====================================================================

@router.post("/register")
async def register_organization(req: RegisterRequest):
    """Register a new organization with an admin employee."""
    if req.email in email_index:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(name=req.org_name)
    admin = Employee(
        org_id=org.id,
        name=req.admin_name,
        email=req.email,
        role=Role.ADMIN,
        password_hash=hash_password(req.password),
        monthly_budget_usd=9999.0
    )
    org.admin_employee_id = admin.id

    organizations[org.id] = org
    employees[admin.id] = admin
    email_index[req.email] = admin.id

    token = create_token(admin.id, org.id, admin.role.value)
    logger.info(f"Registered organization '{org.name}' with admin '{admin.name}'")
    return {
        "token": token,
        "employee": {"id": admin.id, "name": admin.name, "email": admin.email, "role": admin.role.value},
        "organization": {"id": org.id, "name": org.name}
    }


@router.post("/login")
async def login(req: LoginRequest):
    """Authenticate an employee and return a session token."""
    emp_id = email_index.get(req.email)
    if not emp_id:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    emp = employees.get(emp_id)
    if not emp or not verify_password(req.password, emp.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    org = organizations.get(emp.org_id)
    token = create_token(emp.id, emp.org_id, emp.role.value)
    return {
        "token": token,
        "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "role": emp.role.value},
        "organization": {"id": org.id, "name": org.name} if org else None
    }


@router.post("/invite")
async def invite_employee(req: InviteRequest, current: dict = Depends(get_current_employee)):
    """Admin-only: Invite a new employee to the organization."""
    if current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can invite employees")
    if req.email in email_index:
        raise HTTPException(status_code=400, detail="Email already registered")

    temp_password = secrets.token_urlsafe(8)

    emp = Employee(
        org_id=current["org_id"],
        name=req.name,
        email=req.email,
        role=Role(req.role),
        password_hash=hash_password(temp_password),
        monthly_budget_usd=req.monthly_budget_usd
    )
    employees[emp.id] = emp
    email_index[req.email] = emp.id

    logger.info(f"Invited employee '{emp.name}' to org '{current['org_id']}'")
    return {
        "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "role": emp.role.value},
        "temp_password": temp_password
    }


@router.get("/members")
async def list_members(current: dict = Depends(get_current_employee)):
    """List all employees in the current organization."""
    org_id = current["org_id"]
    members = [
        {
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
            "role": emp.role.value,
            "monthly_budget_usd": emp.monthly_budget_usd,
            "tokens_used_this_month": emp.tokens_used_this_month,
            "total_requests": emp.total_requests
        }
        for emp in employees.values() if emp.org_id == org_id
    ]
    return {"members": members}


@router.get("/usage")
async def org_usage(current: dict = Depends(get_current_employee)):
    """Get organization-wide usage analytics."""
    org_id = current["org_id"]
    org = organizations.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_usage = []
    total_tokens = 0
    for emp in employees.values():
        if emp.org_id == org_id:
            budget_pct = (emp.tokens_used_this_month / max(emp.monthly_budget_usd * 1000, 1)) * 100
            member_usage.append({
                "id": emp.id,
                "name": emp.name,
                "tokens_used": emp.tokens_used_this_month,
                "budget_usd": emp.monthly_budget_usd,
                "budget_used_pct": round(min(budget_pct, 100), 1),
                "total_requests": emp.total_requests
            })
            total_tokens += emp.tokens_used_this_month

    return {
        "organization": org.name,
        "total_tokens_used": total_tokens,
        "monthly_budget_usd": org.monthly_budget_usd,
        "members": member_usage
    }


@router.post("/budget")
async def set_budget(req: SetBudgetRequest, current: dict = Depends(get_current_employee)):
    """Admin-only: Set monthly token budget for an employee."""
    if current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can set budgets")
    emp = employees.get(req.employee_id)
    if not emp or emp.org_id != current["org_id"]:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.monthly_budget_usd = req.monthly_budget_usd
    employees[req.employee_id] = emp
    return {"status": "updated", "employee_id": req.employee_id, "new_budget": req.monthly_budget_usd}
