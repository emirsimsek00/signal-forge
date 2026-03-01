from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.webhooks import router as webhooks_router
from backend.config import settings
from backend.database import get_session
from backend.models.signal import Signal


@pytest.fixture
def webhooks_app(db_session):
    app = FastAPI()
    app.include_router(webhooks_router)

    async def _get_session_override():
        yield db_session

    app.dependency_overrides[get_session] = _get_session_override
    return app


@pytest.mark.asyncio
async def test_generic_webhook_requires_valid_secret_and_tenant(webhooks_app, monkeypatch):
    monkeypatch.setattr(settings, "webhook_shared_secret", "test-secret")

    transport = ASGITransport(app=webhooks_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing_secret = await client.post("/api/webhooks/generic", json={"source": "test", "content": "x"})
        bad_secret = await client.post(
            "/api/webhooks/generic",
            headers={"x-webhook-secret": "wrong", "x-tenant-id": "tenant-a"},
            json={"source": "test", "content": "x"},
        )
        missing_tenant = await client.post(
            "/api/webhooks/generic",
            headers={"x-webhook-secret": "test-secret"},
            json={"source": "test", "content": "x"},
        )

    assert missing_secret.status_code == 401
    assert bad_secret.status_code == 401
    assert missing_tenant.status_code == 400


@pytest.mark.asyncio
async def test_generic_webhook_persists_signal_with_header_tenant(webhooks_app, db_session, monkeypatch):
    monkeypatch.setattr(settings, "webhook_shared_secret", "test-secret")

    payload = {
        "source": "partner-system",
        "title": "Latency spike",
        "content": "p95 latency exceeded threshold",
        "metadata": {"region": "us-east-1"},
    }

    transport = ASGITransport(app=webhooks_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/generic",
            headers={"x-webhook-secret": "test-secret", "x-tenant-id": "tenant-123"},
            json=payload,
        )

    assert resp.status_code == 200

    result = await db_session.execute(select(Signal))
    signals = result.scalars().all()
    assert len(signals) == 1
    assert signals[0].tenant_id == "tenant-123"
    assert signals[0].source == "partner-system"


@pytest.mark.asyncio
async def test_webhook_returns_503_when_shared_secret_not_configured(webhooks_app, monkeypatch):
    monkeypatch.setattr(settings, "webhook_shared_secret", "")

    transport = ASGITransport(app=webhooks_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/generic",
            headers={"x-webhook-secret": "anything", "x-tenant-id": "tenant-123"},
            json={"source": "test", "content": "x"},
        )

    assert resp.status_code == 503
