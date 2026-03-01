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


@router.post("/stripe")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Receive Stripe webhook events.

    Verifies the webhook signature if STRIPE_WEBHOOK_SECRET is configured.
    """
    body = await request.body()

    # Optional signature verification
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

    logger.info(f"Stripe webhook received: {event_type}")
    return {"status": "ok", "event_type": event_type}


@router.post("/pagerduty")
async def pagerduty_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Receive PagerDuty webhook v3 events."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", {})
    event_type = event.get("event_type", "unknown")
    incident = event.get("data", {})

    signal = Signal(
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

    logger.info(f"PagerDuty webhook received: {event_type}")
    return {"status": "ok", "event_type": event_type}


@router.post("/generic")
async def generic_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Generic JSON webhook — accepts any JSON payload as a signal.

    Expected format:
    {
        "source": "my-system",
        "title": "Event title",
        "content": "Event description",
        "metadata": { ... }
    }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    source = payload.get("source", "webhook")
    title = payload.get("title", "Webhook event")
    content = payload.get("content", json.dumps(payload))

    signal = Signal(
        source=source,
        source_id=payload.get("id", ""),
        title=title,
        content=content[:2000],
        timestamp=utc_now(),
        metadata_json=json.dumps(payload.get("metadata", {})),
    )
    session.add(signal)
    await session.commit()

    logger.info(f"Generic webhook received from {source}")
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
