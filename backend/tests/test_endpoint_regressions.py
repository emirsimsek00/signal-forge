from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import router as auth_router
from backend.api.brief import router as brief_router
from backend.api.correlation import router as correlation_router
from backend.api.dashboard import router as dashboard_router
from backend.database import get_session
from backend.models.signal import Signal
from backend.models.user import User
from backend.config import settings


@pytest.fixture
def regression_app(db_session: AsyncSession):
    app = FastAPI()

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(brief_router)
    app.include_router(correlation_router)
    return app


@pytest.mark.asyncio
async def test_dashboard_risk_trend_and_brief_generate(regression_app, db_session: AsyncSession):
    db_session.add(
        User(
            supabase_id="sb-a",
            tenant_id="tenant-a",
            email="a@example.com",
            display_name="A",
            role="owner",
        )
    )
    db_session.add_all(
        [
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="CPU spike",
                content="CPU and latency rising",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.3,
                sentiment_label="negative",
                risk_score=0.81,
                risk_tier="critical",
                metadata_json='{"metric_name":"cpu_usage","value":95}',
            ),
            Signal(
                tenant_id="tenant-a",
                source="reddit",
                source_id="a-2",
                title="Users report outage",
                content="multiple outage reports",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.6,
                sentiment_label="negative",
                risk_score=0.65,
                risk_tier="high",
                metadata_json='{"engagement":200}',
            ),
        ]
    )
    await db_session.commit()

    token = jwt.encode({"sub": "1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=regression_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        risk_trend = await client.get("/api/dashboard/risk-trend?hours=24", headers=headers)
        assert risk_trend.status_code == 200
        assert "points" in risk_trend.json()

        brief = await client.get("/api/brief/generate", headers=headers)
        assert brief.status_code == 200
        payload = brief.json()
        assert "situation_overview" in payload
        assert "supporting_metrics" in payload

        correlation_graph = await client.get("/api/correlation/graph/1?depth=1", headers=headers)
        assert correlation_graph.status_code == 200
        graph = correlation_graph.json()
        assert "nodes" in graph and "edges" in graph
