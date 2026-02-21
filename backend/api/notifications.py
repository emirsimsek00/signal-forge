"""Notification preferences and delivery log API."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.api.auth import require_auth, get_tenant_id
from backend.models.user import User
from backend.models.notification import (
    NotificationPreference,
    NotificationPreferenceCreate,
    NotificationPreferenceResponse,
    NotificationLog,
    NotificationLogResponse,
)
from backend.services.notifier import send_email, send_slack, format_signal_email, format_signal_slack

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
logger = logging.getLogger("signalforge.notifications")


@router.get("/preferences")
async def list_preferences(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List notification preferences for the current tenant."""
    result = await session.execute(
        select(NotificationPreference)
        .where(NotificationPreference.tenant_id == tenant_id)
        .order_by(desc(NotificationPreference.created_at))
    )
    prefs = result.scalars().all()
    return {
        "preferences": [
            NotificationPreferenceResponse.model_validate(p).model_dump()
            for p in prefs
        ]
    }


@router.post("/preferences", status_code=201)
async def create_preference(
    body: NotificationPreferenceCreate,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a notification preference."""
    if body.channel not in ("email", "slack"):
        raise HTTPException(status_code=400, detail="Channel must be 'email' or 'slack'")

    valid_triggers = {"critical_signal", "incident_created", "incident_escalated", "incident_resolved", "daily_digest"}
    invalid = set(body.triggers) - valid_triggers
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid triggers: {invalid}")

    pref = NotificationPreference(
        tenant_id=tenant_id,
        channel=body.channel,
        target=body.target,
        triggers=json.dumps(body.triggers),
        is_active=True,
    )
    session.add(pref)
    await session.commit()
    await session.refresh(pref)

    return NotificationPreferenceResponse.model_validate(pref).model_dump()


@router.delete("/preferences/{pref_id}")
async def delete_preference(
    pref_id: int,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete a notification preference."""
    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.id == pref_id,
            NotificationPreference.tenant_id == tenant_id,
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    await session.delete(pref)
    await session.commit()
    return {"status": "deleted"}


@router.get("/log")
async def list_logs(
    limit: int = 50,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """View notification delivery log."""
    result = await session.execute(
        select(NotificationLog)
        .where(NotificationLog.tenant_id == tenant_id)
        .order_by(desc(NotificationLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            NotificationLogResponse.model_validate(lg).model_dump()
            for lg in logs
        ]
    }


@router.post("/test")
async def test_notification(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Send a test notification.

    Body: { channel: "email"|"slack", target: "email@example.com"|"https://hooks.slack..." }
    """
    channel = body.get("channel", "")
    target = body.get("target", "")

    if channel not in ("email", "slack"):
        raise HTTPException(status_code=400, detail="Channel must be 'email' or 'slack'")
    if not target:
        raise HTTPException(status_code=400, detail="Target required")

    test_signal = {
        "title": "Test Signal — SignalForge Notification Check",
        "source": "system",
        "risk_score": 0.85,
        "risk_tier": "high",
        "summary": "This is a test notification from SignalForge to verify your notification channel is configured correctly.",
    }

    try:
        if channel == "email":
            subject, html = format_signal_email(test_signal)
            result = await send_email(target, subject, html)
        else:
            payload = format_signal_slack(test_signal)
            result = await send_slack(target, payload)

        # Log it
        log = NotificationLog(
            tenant_id=tenant_id,
            channel=channel,
            trigger="test",
            subject="Test notification",
            status="sent",
        )
        session.add(log)
        await session.commit()

        return {"status": "sent", "result": result}

    except Exception as exc:
        log = NotificationLog(
            tenant_id=tenant_id,
            channel=channel,
            trigger="test",
            subject="Test notification",
            status="failed",
            error=str(exc),
        )
        session.add(log)
        await session.commit()

        raise HTTPException(status_code=500, detail=f"Notification failed: {exc}")
