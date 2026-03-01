from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.signals import router as signals_router
from backend.api.incidents import router as incidents_router
from backend.api.dashboard import router as dashboard_router
from backend.api.forecast import router as forecast_router
from backend.api.correlation import router as correlation_router
from backend.api.simulator import router as simulator_router
from backend.api.brief import router as brief_router
from backend.api.chat import router as chat_router


@pytest.fixture
def protected_routes_app():
    app = FastAPI()
    app.include_router(signals_router)
    app.include_router(incidents_router)
    app.include_router(dashboard_router)
    app.include_router(forecast_router)
    app.include_router(correlation_router)
    app.include_router(simulator_router)
    app.include_router(brief_router)
    app.include_router(chat_router)
    return app


@pytest.mark.asyncio
async def test_remaining_read_write_routes_require_auth(protected_routes_app):
    transport = ASGITransport(app=protected_routes_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.get("/api/signals"),
            await client.get("/api/incidents"),
            await client.get("/api/dashboard/overview"),
            await client.get("/api/forecast"),
            await client.get("/api/correlation/1"),
            await client.post("/api/simulator/run", json={}),
            await client.get("/api/brief/generate"),
            await client.post("/api/incidents/1/acknowledge"),
        ]

    assert all(r.status_code == 401 for r in responses)
