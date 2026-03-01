"""Webhook endpoints for real-time event ingestion from external services."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from backend.utils.time import utc_now

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from backend.config import settings
from backend.database import get_session
from backend.models.signal import Signal

logger = logging.getLogger("signalforge.webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

WEBHOOK_SECRET_HEADER = "x-webhook-secret"
WEBHOOK_TENANT_HEADER = "x-tenant-id"


def _validate_webhook_access(request: Request) -> str:
    """Validate shared-secret auth and tenant binding for inbound webhooks.

    Returns tenant_id on success.
    """
    configured_secret = (settings.webhook_shared_secret or "").strip()
    if not configured_secret:
        logger.error("Webhook request rejected: WEBHOOK_SHARED_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Webhook ingestion is not configured")

    provided_secret = (request.headers.get(WEBHOOK_SECRET_HEADER) or "").strip()
    if not provided_secret or not hmac.compare_digest(configured_secret, provided_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    tenant_id = (request.headers.get(WEBHOOK_TENANT_HEADER) or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant header")

    if len(tenant_id) > 36:
        raise HTTPException(status_code=400, detail="Invalid tenant header")

    return tenant_id


@router.post("/stripe")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Receive Stripe webhook events.

    Requires shared-secret auth + tenant header.
    Verifies Stripe signature when STRIPE_WEBHOOK_SECRET is configured.
    """
    tenant_id = _validate_webhook_access(request)
    body = await request.body()

    # Optional Stripe signature verification
    stripe_sig = request.headers.get("stripe-signature", "")
    webhook_secret = getattr(settings, "stripe_webhook_secret", "")
    if webhook_secret and stripe_sig:
        if not _verify_stripe_signature(body, stripe_sig, webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("type", "unknown")
    data_obj = payload.get("data", {}).get("object", {})

    signal = Signal(
        tenant_id=tenant_id,
        source="stripe",
        source_id=payload.get("id", ""),
        title=f"Stripe: {event_type}",
        content=json.dumps(data_obj)[:2000],
        timestamp=utc_now(),
        metadata_json=json.dumps({
            "event_type": event_type,
            "amount": data_obj.get("amount", 0),
            "currency": data_obj.get("currency", ""),
            "webhook": True,
        }),
    )
    session.add(signal)
    await session.commit()

    logger.info(f"Stripe webhook received: {event_type} (tenant={tenant_id})")
    return {"status": "ok", "event_type": event_type}


@router.post("/pagerduty")
async def pagerduty_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Receive PagerDuty webhook v3 events.

    Requires shared-secret auth + tenant header.
    """
    tenant_id = _validate_webhook_access(request)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", {})
    event_type = event.get("event_type", "unknown")
    incident = event.get("data", {})

    signal = Signal(
        tenant_id=tenant_id,
        source="pagerduty",
        source_id=incident.get("id", ""),
        title=incident.get("title", f"PagerDuty: {event_type}"),
        content=incident.get("description", incident.get("title", "PagerDuty event")),
        timestamp=utc_now(),
        metadata_json=json.dumps({
            "event_type": event_type,
            "status": incident.get("status", ""),
            "urgency": incident.get("urgency", ""),
            "service": incident.get("service", {}).get("summary", ""),
            "webhook": True,
        }),
    )
    session.add(signal)
    await session.commit()

    logger.info(f"PagerDuty webhook received: {event_type} (tenant={tenant_id})")
    return {"status": "ok", "event_type": event_type}


@router.post("/generic")
async def generic_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Generic JSON webhook — accepts any JSON payload as a signal.

    Requires shared-secret auth + tenant header.

    Expected payload format:
    {
        "source": "my-system",
        "title": "Event title",
        "content": "Event description",
        "metadata": { ... }
    }
    """
    tenant_id = _validate_webhook_access(request)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    source = payload.get("source", "webhook")
    title = payload.get("title", "Webhook event")
    content = payload.get("content", json.dumps(payload))

    signal = Signal(
        tenant_id=tenant_id,
        source=source,
        source_id=payload.get("id", ""),
        title=title,
        content=content[:2000],
        timestamp=utc_now(),
        metadata_json=json.dumps(payload.get("metadata", {})),
    )
    session.add(signal)
    await session.commit()

    logger.info(f"Generic webhook received from {source} (tenant={tenant_id})")
    return {"status": "ok", "source": source}


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe webhook signature (simplified v1 check)."""
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False
