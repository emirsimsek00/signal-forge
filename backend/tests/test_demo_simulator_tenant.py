"""Tenant-scoping tests for demo seeding/reset and simulator."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

from backend.api.demo import reset_demo_data, seed_demo_data
from backend.api.simulator import ScenarioRequest, run_scenario
from backend.models.incident import Incident
from backend.models.risk import RiskAssessment
from backend.models.signal import Signal


@pytest.mark.asyncio
async def test_seed_demo_data_assigns_tenant(db_session):
    result = await seed_demo_data(tenant_id="tenant-a", session=db_session)
    assert result["status"] in {"success", "already_seeded"}

    signal_count = (
        await db_session.execute(
            select(func.count(Signal.id)).where(Signal.tenant_id == "tenant-a")
        )
    ).scalar() or 0
    incident_count = (
        await db_session.execute(
            select(func.count(Incident.id)).where(Incident.tenant_id == "tenant-a")
        )
    ).scalar() or 0
    risk_count = (
        await db_session.execute(
            select(func.count(RiskAssessment.id)).where(RiskAssessment.tenant_id == "tenant-a")
        )
    ).scalar() or 0

    assert signal_count > 0
    assert incident_count > 0
    assert risk_count > 0


@pytest.mark.asyncio
async def test_reset_demo_data_only_affects_current_tenant(db_session):
    await seed_demo_data(tenant_id="tenant-a", session=db_session)
    await seed_demo_data(tenant_id="tenant-b", session=db_session)

    reset_result = await reset_demo_data(tenant_id="tenant-a", session=db_session)
    assert reset_result["status"] == "success"

    tenant_a_signals = (
        await db_session.execute(
            select(func.count(Signal.id)).where(
                Signal.tenant_id == "tenant-a",
                Signal.source_id.like("demo-%"),
            )
        )
    ).scalar() or 0
    tenant_b_signals = (
        await db_session.execute(
            select(func.count(Signal.id)).where(
                Signal.tenant_id == "tenant-b",
                Signal.source_id.like("demo-%"),
            )
        )
    ).scalar() or 0

    assert tenant_a_signals == 0
    assert tenant_b_signals > 0


@pytest.mark.asyncio
async def test_simulator_scopes_to_tenant(db_session):
    db_session.add_all(
        [
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="A Signal",
                content="Tenant A signal",
                timestamp=datetime.utcnow(),
                sentiment_score=-0.2,
                risk_score=0.6,
                risk_tier="high",
            ),
            Signal(
                tenant_id="tenant-b",
                source="system",
                source_id="b-1",
                title="B Signal",
                content="Tenant B signal",
                timestamp=datetime.utcnow(),
                sentiment_score=0.4,
                risk_score=0.2,
                risk_tier="low",
            ),
        ]
    )
    await db_session.commit()

    result_a = await run_scenario(
        request=ScenarioRequest(),
        tenant_id="tenant-a",
        session=db_session,
    )
    result_b = await run_scenario(
        request=ScenarioRequest(),
        tenant_id="tenant-b",
        session=db_session,
    )

    assert result_a.signals_analyzed == 1
    assert result_b.signals_analyzed == 1
