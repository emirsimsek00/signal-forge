"""Authentication API — Supabase Auth integration with multi-tenancy.

When SUPABASE_URL is configured, JWT tokens from Supabase are validated
and mapped to local User/Tenant rows. When not configured, a lightweight
demo mode allows unauthenticated access with a default tenant.
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.models.user import User, UserResponse, TokenResponse
from backend.models.tenant import Tenant, TenantResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("signalforge.auth")

security = HTTPBearer(auto_error=False)

# ── Supabase detection ────────────────────────────────────────

_supabase_enabled = bool(settings.supabase_url and settings.supabase_anon_key)

DEFAULT_TENANT_ID = "default"
DEFAULT_TENANT_NAME = "Default Workspace"


# ── JWT verification ──────────────────────────────────────────

def _verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued JWT and return its payload."""
    secret = settings.supabase_jwt_secret or settings.jwt_secret
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


# ── Dependency: get current user ──────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Extract and validate user from JWT (Supabase or legacy).

    Returns None if no token is provided (allows optional auth).
    In demo mode (no Supabase configured), returns None (all data uses default tenant).
    """
    if credentials is None:
        return None

    token = credentials.credentials

    if _supabase_enabled:
        payload = _verify_supabase_jwt(token)
        supabase_id = payload.get("sub", "")
        email = payload.get("email", "")
        if not supabase_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        # Look up or auto-create local user row
        result = await session.execute(
            select(User).where(User.supabase_id == supabase_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # First login — auto-provision with default tenant
            user = User(
                supabase_id=supabase_id,
                tenant_id=DEFAULT_TENANT_ID,
                email=email,
                display_name=email.split("@")[0],
                role="owner",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"Auto-provisioned user {email} (supabase_id={supabase_id})")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")

        return user
    else:
        # Legacy JWT mode (dev/demo)
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            user_id = int(payload.get("sub", 0))
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
        except (JWTError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user


async def require_auth(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Strict auth dependency — rejects unauthenticated requests."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: str):
    """Factory for role-checking dependencies."""
    async def _check(user: User = Depends(require_auth)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {', '.join(roles)}"
            )
        return user
    return _check


require_admin = require_role("admin", "owner")


# ── Tenant resolution ────────────────────────────────────────

def get_tenant_id(user: Optional[User] = Depends(get_current_user)) -> str:
    """Resolve tenant_id — from authenticated user or default."""
    if user is not None:
        return user.tenant_id
    return DEFAULT_TENANT_ID


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/callback")
async def auth_callback(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Called after Supabase signup to create tenant + local user.

    Body: { supabase_id, email, display_name?, tenant_name? }
    """
    supabase_id = body.get("supabase_id", "")
    email = body.get("email", "")
    display_name = body.get("display_name", email.split("@")[0] if email else "User")
    tenant_name = body.get("tenant_name", f"{display_name}'s Workspace")

    if not supabase_id or not email:
        raise HTTPException(status_code=400, detail="supabase_id and email required")

    # Check if user already exists
    existing = await session.execute(
        select(User).where(User.supabase_id == supabase_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already provisioned")

    # Create tenant
    slug = re.sub(r"[^a-z0-9]+", "-", tenant_name.lower()).strip("-")
    # Check slug uniqueness, append random suffix if needed
    slug_check = await session.execute(select(Tenant).where(Tenant.slug == slug))
    if slug_check.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    tenant = Tenant(name=tenant_name, slug=slug)
    session.add(tenant)
    await session.flush()  # get tenant.id

    # Create user
    user = User(
        supabase_id=supabase_id,
        tenant_id=tenant.id,
        email=email,
        display_name=display_name,
        role="owner",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await session.refresh(tenant)

    logger.info(f"Created tenant '{tenant.name}' and user {email}")

    return {
        "user": UserResponse.model_validate(user).model_dump(),
        "tenant": TenantResponse.model_validate(tenant).model_dump(),
    }


@router.post("/join")
async def join_tenant(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Join an existing tenant by invite code (tenant slug).

    Body: { supabase_id, email, tenant_slug, display_name? }
    """
    supabase_id = body.get("supabase_id", "")
    email = body.get("email", "")
    tenant_slug = body.get("tenant_slug", "")
    display_name = body.get("display_name", email.split("@")[0] if email else "User")

    if not supabase_id or not email or not tenant_slug:
        raise HTTPException(status_code=400, detail="supabase_id, email, and tenant_slug required")

    # Find tenant
    result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Check if user already exists
    existing = await session.execute(
        select(User).where(User.supabase_id == supabase_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already provisioned")

    user = User(
        supabase_id=supabase_id,
        tenant_id=tenant.id,
        email=email,
        display_name=display_name,
        role="analyst",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return {
        "user": UserResponse.model_validate(user).model_dump(),
        "tenant": TenantResponse.model_validate(tenant).model_dump(),
    }


@router.get("/me")
async def get_me(
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Return current user info with tenant."""
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()

    return {
        "user": UserResponse.model_validate(user).model_dump(),
        "tenant": TenantResponse.model_validate(tenant).model_dump() if tenant else None,
    }
