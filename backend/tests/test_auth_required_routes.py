from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.notifications import router as notifications_router
from backend.api.settings import router as settings_router
from backend.api.demo import router as demo_router


@pytest.fixture
def auth_required_app():
    app = FastAPI()
    app.include_router(notifications_router)
    app.include_router(settings_router)
    app.include_router(demo_router)
    return app


@pytest.mark.asyncio
async def test_notifications_settings_demo_require_auth(auth_required_app):
    transport = ASGITransport(app=auth_required_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/api/notifications/preferences")
        r2 = await client.get("/api/settings")
        r3 = await client.post("/api/demo/seed")

    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r3.status_code == 401
