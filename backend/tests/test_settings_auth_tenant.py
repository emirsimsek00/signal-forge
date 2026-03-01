from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import router as auth_router
from backend.api.settings import router as settings_router
from backend.config import settings
from backend.database import get_session
from backend.models.user import User


@pytest.fixture
def settings_app(db_session: AsyncSession, tmp_path, monkeypatch):
    app = FastAPI()

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.include_router(auth_router)
    app.include_router(settings_router)

    settings_file = tmp_path / "user_settings.json"
    from backend.api import settings as settings_api

    monkeypatch.setattr(settings_api, "_SETTINGS_FILE", str(settings_file))
    return app


@pytest.mark.asyncio
async def test_settings_requires_auth(settings_app, db_session):
    transport = ASGITransport(app=settings_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/settings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_settings_are_tenant_scoped(settings_app, db_session, tmp_path):
    db_session.add_all(
        [
            User(supabase_id="sb-a", tenant_id="tenant-a", email="a@example.com", display_name="A", role="owner"),
            User(supabase_id="sb-b", tenant_id="tenant-b", email="b@example.com", display_name="B", role="owner"),
        ]
    )
    await db_session.commit()

    token_a = jwt.encode({"sub": "1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    token_b = jwt.encode({"sub": "2"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    payload_a = {
        "sentiment": 0.30,
        "anomaly": 0.30,
        "ticket_volume": 0.15,
        "revenue": 0.15,
        "engagement": 0.10,
    }

    transport = ASGITransport(app=settings_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        update_a = await client.put(
            "/api/settings/risk-weights",
            headers={"Authorization": f"Bearer {token_a}"},
            json=payload_a,
        )
        assert update_a.status_code == 200

        get_a = await client.get("/api/settings/risk-weights", headers={"Authorization": f"Bearer {token_a}"})
        get_b = await client.get("/api/settings/risk-weights", headers={"Authorization": f"Bearer {token_b}"})

    assert get_a.status_code == 200
    assert get_b.status_code == 200
    assert get_a.json()["sentiment"] == 0.30
    assert get_b.json()["sentiment"] == 0.25
