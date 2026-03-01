"""Security and tenant-scope regression tests."""

from __future__ import annotations

from datetime import datetime

from backend.utils.time import utc_now

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api import auth as auth_api
from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.dashboard import router as dashboard_router
from backend.api.forecast import router as forecast_router
from backend.database import get_session
from backend.models.signal import Signal
from backend.models.user import User


@pytest.fixture
def secure_test_app(db_session: AsyncSession):
    app = FastAPI()

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(dashboard_router)
    app.include_router(forecast_router)
    return app


@pytest.mark.asyncio
async def test_auth_callback_requires_token_in_supabase_mode(secure_test_app, monkeypatch):
    monkeypatch.setattr(auth_api, "_supabase_enabled", True)

    transport = ASGITransport(app=secure_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/callback", json={"tenant_name": "Acme"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_callback_rejects_identity_mismatch(secure_test_app, monkeypatch):
    monkeypatch.setattr(auth_api, "_supabase_enabled", True)
    monkeypatch.setattr(
        auth_api,
        "_verify_supabase_jwt",
        lambda _token: {
            "sub": "sb-user-1",
            "email": "owner@example.com",
            "user_metadata": {"display_name": "Owner"},
        },
    )

    transport = ASGITransport(app=secure_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/callback",
            headers={"Authorization": "Bearer fake-token"},
            json={"email": "attacker@example.com"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_scoped_chat_dashboard_and_forecast(secure_test_app, db_session, monkeypatch):
    monkeypatch.setattr(auth_api, "_supabase_enabled", False)
    db_session.add_all(
        [
            User(
                supabase_id="sb-a",
                tenant_id="tenant-a",
                email="a@example.com",
                display_name="A",
                role="owner",
            ),
            User(
                supabase_id="sb-b",
                tenant_id="tenant-b",
                email="b@example.com",
                display_name="B",
                role="owner",
            ),
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="CPU spike A",
                content="Tenant A alert",
                timestamp=utc_now(),
                sentiment_score=-0.2,
                sentiment_label="negative",
                risk_score=0.8,
                risk_tier="critical",
                metadata_json='{"metric_name":"cpu_usage","value":90}',
            ),
            Signal(
                tenant_id="tenant-b",
                source="system",
                source_id="b-1",
                title="CPU spike B",
                content="Tenant B alert",
                timestamp=utc_now(),
                sentiment_score=0.1,
                sentiment_label="neutral",
                risk_score=0.2,
                risk_tier="low",
                metadata_json='{"metric_name":"cpu_usage","value":40}',
            ),
        ]
    )
    await db_session.commit()

    transport = ASGITransport(app=secure_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Bypass JWT complexity in test by using legacy JWT mode and known user IDs.
        from backend.config import settings
        from jose import jwt

        token_a = jwt.encode({"sub": "1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        token_b = jwt.encode({"sub": "2"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        dashboard_a = await client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token_a}"})
        dashboard_b = await client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token_b}"})

        chat_a = await client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"query": "show critical signals"},
        )
        chat_b = await client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"query": "show critical signals"},
        )

        forecast_a = await client.get(
            "/api/forecast?metric_name=cpu_usage&horizon=4&lookback_hours=24",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        forecast_b = await client.get(
            "/api/forecast?metric_name=cpu_usage&horizon=4&lookback_hours=24",
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert dashboard_a.status_code == 200
    assert dashboard_b.status_code == 200
    assert dashboard_a.json()["total_signals"] == 1
    assert dashboard_b.json()["total_signals"] == 1

    assert chat_a.status_code == 200
    assert chat_b.status_code == 200
    assert chat_a.json()["signal_count"] == 1
    assert chat_b.json()["signal_count"] == 0

    assert forecast_a.status_code == 200
    assert forecast_b.status_code == 200
    assert forecast_a.json()["observed_points"]
    assert forecast_b.json()["observed_points"]
