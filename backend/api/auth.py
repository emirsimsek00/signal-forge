"""Authentication API — Supabase Auth integration with multi-tenancy.

When SUPABASE_URL is configured, JWT tokens from Supabase are validated
and mapped to local User/Tenant rows. When not configured, a lightweight
demo mode allows unauthenticated access with a default tenant.
"""

from __future__ import annotations

import re
import uuid
import logging
import json
import time
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.models.user import User, UserResponse
from backend.models.tenant import Tenant, TenantResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("signalforge.auth")

security = HTTPBearer(auto_error=False)

# ── Supabase detection ────────────────────────────────────────

_supabase_enabled = bool(settings.supabase_url and settings.supabase_anon_key)

DEFAULT_TENANT_ID = "default"
DEFAULT_TENANT_NAME = "Default Workspace"
_JWKS_CACHE: dict[str, object] = {"fetched_at": 0.0, "keys": []}
_JWKS_CACHE_TTL_SECONDS = 300


# ── JWT verification ──────────────────────────────────────────

def _verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued JWT and return its payload."""
    try:
        header = jwt.get_unverified_header(token)
        alg = str(header.get("alg") or "").upper()

        if alg == "HS256":
            secret = settings.supabase_jwt_secret or settings.jwt_secret
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        elif alg in {"RS256", "ES256", "EDDSA"}:
            kid = str(header.get("kid") or "").strip()
            if not kid:
                raise HTTPException(status_code=401, detail="Invalid token: missing key id")
            jwk_key = _get_supabase_jwk(kid)
            payload = jwt.decode(
                token,
                jwk_key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        else:
            raise HTTPException(status_code=401, detail=f"Invalid token: unsupported alg '{alg}'")

        # Minimal issuer hardening.
        iss = _safe_str(payload.get("iss"))
        expected_iss = f"{settings.supabase_url.rstrip('/')}/auth/v1"
        if iss and settings.supabase_url and iss.rstrip("/") != expected_iss:
            raise HTTPException(status_code=401, detail="Invalid token: issuer mismatch")

        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def _fetch_supabase_jwks() -> list[dict]:
    now = time.time()
    cached_at = float(_JWKS_CACHE.get("fetched_at") or 0.0)
    cached_keys = _JWKS_CACHE.get("keys")
    if isinstance(cached_keys, list) and cached_keys and now - cached_at < _JWKS_CACHE_TTL_SECONDS:
        return cached_keys

    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        with urllib_request.urlopen(jwks_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: unable to fetch signing keys ({exc})")

    keys = payload.get("keys", []) if isinstance(payload, dict) else []
    if not isinstance(keys, list) or not keys:
        raise HTTPException(status_code=401, detail="Invalid token: signing keys unavailable")

    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["fetched_at"] = now
    return keys


def _get_supabase_jwk(kid: str) -> dict:
    keys = _fetch_supabase_jwks()
    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    raise HTTPException(status_code=401, detail="Invalid token: unknown signing key")


def _slugify_workspace(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or f"workspace-{uuid.uuid4().hex[:8]}"


def _safe_str(value: object, fallback: str = "") -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else fallback
    return fallback


def _extract_supabase_identity_from_payload(payload: dict) -> tuple[str, str]:
    supabase_id = _safe_str(payload.get("sub"))
    email = _safe_str(payload.get("email")).lower()
    if not supabase_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return supabase_id, email


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
        supabase_id, email = _extract_supabase_identity_from_payload(payload)

        # Look up or auto-create local user row
        result = await session.execute(
            select(User).where(User.supabase_id == supabase_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # First login — auto-provision a tenant from token metadata when possible.
            metadata = payload.get("user_metadata", {}) if isinstance(payload.get("user_metadata"), dict) else {}
            display_name = _safe_str(metadata.get("display_name"), email.split("@")[0])
            workspace_name = _safe_str(
                metadata.get("workspace_name"),
                f"{display_name}'s Workspace",
            )
            slug = _slugify_workspace(workspace_name)
            slug_check = await session.execute(select(Tenant).where(Tenant.slug == slug))
            if slug_check.scalar_one_or_none():
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"

            tenant = Tenant(name=workspace_name, slug=slug)
            session.add(tenant)
            await session.flush()

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
            logger.info(
                "Auto-provisioned user %s (supabase_id=%s) in tenant %s",
                email,
                supabase_id,
                tenant.id,
            )

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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
):
    """Called after Supabase signup to create tenant + local user.

    Body: { display_name?, tenant_name? }
    """
    if _supabase_enabled:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        payload = _verify_supabase_jwt(credentials.credentials)
        supabase_id, email = _extract_supabase_identity_from_payload(payload)
        metadata = payload.get("user_metadata", {}) if isinstance(payload.get("user_metadata"), dict) else {}
        default_display_name = _safe_str(metadata.get("display_name"), email.split("@")[0])
        default_tenant_name = _safe_str(
            metadata.get("workspace_name"),
            f"{default_display_name}'s Workspace",
        )

        body_supabase_id = _safe_str(body.get("supabase_id"))
        body_email = _safe_str(body.get("email")).lower()
        if body_supabase_id and body_supabase_id != supabase_id:
            raise HTTPException(status_code=403, detail="supabase_id does not match auth token")
        if body_email and body_email != email:
            raise HTTPException(status_code=403, detail="email does not match auth token")

        display_name = _safe_str(body.get("display_name"), default_display_name)
        tenant_name = _safe_str(body.get("tenant_name"), default_tenant_name)
    else:
        supabase_id = _safe_str(body.get("supabase_id"))
        email = _safe_str(body.get("email")).lower()
        if not supabase_id or not email:
            raise HTTPException(status_code=400, detail="supabase_id and email required")
        display_name = _safe_str(body.get("display_name"), email.split("@")[0])
        tenant_name = _safe_str(body.get("tenant_name"), f"{display_name}'s Workspace")

    # Check if user already exists
    existing = await session.execute(
        select(User).where(User.supabase_id == supabase_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already provisioned")

    # Create tenant
    slug = _slugify_workspace(tenant_name)
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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
):
    """Join an existing tenant by invite code (tenant slug).

    Body: { tenant_slug, display_name? }
    """
    tenant_slug = _safe_str(body.get("tenant_slug"))

    if _supabase_enabled:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        payload = _verify_supabase_jwt(credentials.credentials)
        supabase_id, email = _extract_supabase_identity_from_payload(payload)
        metadata = payload.get("user_metadata", {}) if isinstance(payload.get("user_metadata"), dict) else {}
        default_display_name = _safe_str(metadata.get("display_name"), email.split("@")[0])

        body_supabase_id = _safe_str(body.get("supabase_id"))
        body_email = _safe_str(body.get("email")).lower()
        if body_supabase_id and body_supabase_id != supabase_id:
            raise HTTPException(status_code=403, detail="supabase_id does not match auth token")
        if body_email and body_email != email:
            raise HTTPException(status_code=403, detail="email does not match auth token")

        display_name = _safe_str(body.get("display_name"), default_display_name)
    else:
        supabase_id = _safe_str(body.get("supabase_id"))
        email = _safe_str(body.get("email")).lower()
        display_name = _safe_str(body.get("display_name"), email.split("@")[0] if email else "User")
        if not supabase_id or not email:
            raise HTTPException(status_code=400, detail="supabase_id and email required")

    if not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug required")

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
