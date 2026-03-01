"""Tests for scheduler daily digest helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.utils.time import utc_now

import pytest

from backend.models.incident import Incident
from backend.models.signal import Signal
from backend.workers.scheduler import BackgroundScheduler


@pytest.mark.asyncio
async def test_build_daily_digest_context_scopes_to_tenant(db_session):
    now = utc_now()
    window_ts = now - timedelta(hours=1)

    db_session.add_all(
        [
            Signal(
                tenant_id="tenant-a",
                source="system",
                source_id="a-1",
                title="A critical signal",
                content="A critical signal",
                timestamp=window_ts,
                risk_score=0.9,
                risk_tier="critical",
            ),
            Signal(
                tenant_id="tenant-b",
                source="system",
                source_id="b-1",
                title="B signal",
                content="B signal",
                timestamp=window_ts,
                risk_score=0.2,
                risk_tier="low",
            ),
            Incident(
                tenant_id="tenant-a",
                title="A incident",
                description="A incident",
                severity="high",
                status="active",
                start_time=window_ts,
            ),
            Incident(
                tenant_id="tenant-b",
                title="B incident",
                description="B incident",
                severity="low",
                status="active",
                start_time=window_ts,
            ),
        ]
    )
    await db_session.commit()

    scheduler = BackgroundScheduler()
    digest = await scheduler._build_daily_digest_context(
        session=db_session,
        tenant_id="tenant-a",
        now=now,
    )

    assert digest["total_signals"] == 1
    assert digest["critical_signals"] == 1
    assert digest["active_incidents"] == 1
    assert digest["new_incidents"] == 1
    assert len(digest["top_signals"]) == 1


def test_should_send_daily_digest_once_per_day():
    scheduler = BackgroundScheduler()
    now = datetime(2026, 2, 21, 10, 0, 0)

    assert scheduler._should_send_daily_digest("tenant-a", now) is True
    scheduler._last_daily_digest_sent["tenant-a"] = now

    assert scheduler._should_send_daily_digest("tenant-a", now + timedelta(hours=5)) is False
    assert scheduler._should_send_daily_digest("tenant-a", now + timedelta(days=1)) is True
