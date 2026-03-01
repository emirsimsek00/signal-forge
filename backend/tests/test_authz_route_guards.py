"""Authorization regression tests for tenant isolation on route-level resources."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import router as auth_router
from backend.api.signals import router as signals_router
from backend.api.incidents import router as incidents_router
from backend.api.correlation import router as correlation_router
from backend.config import settings
from backend.database import get_session
from backend.models.incident import Incident
from backend.models.signal import Signal
from backend.models.user import User


@pytest.fixture
def route_guard_app(db_session: AsyncSession):
    app = FastAPI()

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.include_router(auth_router)
    app.include_router(signals_router)
    app.include_router(incidents_router)
    app.include_router(correlation_router)
    return app


@pytest.mark.asyncio
async def test_cross_tenant_signal_and_incident_access_is_blocked(route_guard_app, db_session):
    # tenant-a user -> id=1, tenant-b user -> id=2
    db_session.add_all(
        [
            User(supabase_id="sb-a", tenant_id="tenant-a", email="a@example.com", display_name="A", role="owner"),
            User(supabase_id="sb-b", tenant_id="tenant-b", email="b@example.com", display_name="B", role="owner"),
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="A signal",
                content="tenant a signal",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.2,
                sentiment_label="negative",
                risk_score=0.9,
                risk_tier="critical",
            ),
            Incident(
                tenant_id="tenant-a",
                title="A incident",
                description="tenant a incident",
                severity="high",
                status="active",
                start_time=datetime.utcnow(),
                related_signal_ids_json="[]",
            ),
        ]
    )
    await db_session.commit()

    token_b = jwt.encode({"sub": "2"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    transport = ASGITransport(app=route_guard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        signal_resp = await client.get("/api/signals/1", headers={"Authorization": f"Bearer {token_b}"})
        incident_resp = await client.get("/api/incidents/1", headers={"Authorization": f"Bearer {token_b}"})

    assert signal_resp.status_code == 404
    assert incident_resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_correlation_returns_no_data(route_guard_app, db_session):
    db_session.add_all(
        [
            User(supabase_id="sb-a", tenant_id="tenant-a", email="a@example.com", display_name="A", role="owner"),
            User(supabase_id="sb-b", tenant_id="tenant-b", email="b@example.com", display_name="B", role="owner"),
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="A signal",
                content="tenant a signal",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.2,
                sentiment_label="negative",
                embedding_json="[0.1,0.2,0.3]",
            ),
            Signal(
                tenant_id="tenant-a",
                source="reddit",
                source_id="a-2",
                title="A signal 2",
                content="tenant a signal 2",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.1,
                sentiment_label="negative",
                embedding_json="[0.11,0.2,0.29]",
            ),
        ]
    )
    await db_session.commit()

    token_b = jwt.encode({"sub": "2"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    transport = ASGITransport(app=route_guard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/correlation/1?k=5", headers={"Authorization": f"Bearer {token_b}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["signal_id"] == 1
    assert data["total"] == 0
    assert data["correlations"] == []
