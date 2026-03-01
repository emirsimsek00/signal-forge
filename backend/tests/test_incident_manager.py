"""Tests for automatic incident generation."""

import json
from datetime import datetime, timedelta

from backend.utils.time import utc_now

import pytest
from sqlalchemy import select

from backend.anomaly.detector import AnomalyEvent
from backend.incident_manager import AutoIncidentManager
from backend.models.incident import Incident
from backend.models.signal import Signal


class TestAutoIncidentManager:
    @pytest.mark.asyncio
    async def test_create_from_anomalies(self, db_session):
        manager = AutoIncidentManager()
        anomaly = AnomalyEvent(
            id="a-1",
            type="risk_spike",
            severity="high",
            title="Risk spike detected",
            description="Risk moved above baseline",
            affected_source="reddit",
            metric_value=0.8,
            threshold=0.5,
            affected_signal_ids=[101, 102],
            detected_at=utc_now(),
        )

        created = await manager.create_from_anomalies(db_session, [anomaly])
        await db_session.commit()

        assert len(created) == 1
        incident = created[0]
        assert incident.title.startswith("[Anomaly]")
        assert incident.severity in {"high", "medium", "critical"}
        assert incident.related_signal_ids_json is not None

    @pytest.mark.asyncio
    async def test_anomaly_dedup_updates_existing_incident(self, db_session):
        manager = AutoIncidentManager()
        first = AnomalyEvent(
            id="a-2",
            type="volume_spike",
            severity="moderate",
            title="Volume spike: reddit",
            description="Volume spike observed",
            affected_source="reddit",
            metric_value=15.0,
            threshold=8.0,
            affected_signal_ids=[1, 2],
            detected_at=utc_now() - timedelta(minutes=5),
        )
        second = AnomalyEvent(
            id="a-3",
            type="volume_spike",
            severity="critical",
            title="Volume spike: reddit",
            description="Volume spike worsened",
            affected_source="reddit",
            metric_value=40.0,
            threshold=8.0,
            affected_signal_ids=[3, 4],
            detected_at=utc_now(),
        )

        created_first = await manager.create_from_anomalies(db_session, [first])
        created_second = await manager.create_from_anomalies(db_session, [second])
        await db_session.commit()

        assert len(created_first) == 1
        assert len(created_second) == 0

        result = await db_session.execute(select(Incident).where(Incident.title.like("[Anomaly]%")))
        incidents = result.scalars().all()
        assert len(incidents) == 1
        assert incidents[0].severity == "critical"
        related_ids = json.loads(incidents[0].related_signal_ids_json or "[]")
        assert set(related_ids) >= {1, 2, 3, 4}

    @pytest.mark.asyncio
    async def test_create_from_forecasts(self, db_session):
        # Build a clearly declining revenue metric.
        now = utc_now()
        for i in range(12):
            value = 150000 - (i * 3500)
            db_session.add(
                Signal(
                    source="financial",
                    source_id=f"mrr-{i}",
                    title=f"MRR {i}",
                    content="Revenue metric",
                    timestamp=now - timedelta(hours=12 - i),
                    metadata_json=json.dumps({"metric_name": "mrr", "value": value}),
                )
            )
        await db_session.commit()

        manager = AutoIncidentManager()
        created = await manager.create_from_forecasts(
            session=db_session,
            max_metrics=3,
            lookback_hours=48,
            horizon=6,
        )
        await db_session.commit()

        assert len(created) >= 1
        assert any("mrr" in incident.title.lower() for incident in created)

        result = await db_session.execute(select(Incident))
        incidents = result.scalars().all()
        assert len(incidents) >= 1

    @pytest.mark.asyncio
    async def test_reconcile_open_incidents_resolves_stale_anomaly(self, db_session):
        manager = AutoIncidentManager()
        incident = Incident(
            title="[Anomaly] Risk spike detected",
            description="Test",
            severity="high",
            status="investigating",
            start_time=utc_now() - timedelta(hours=5),
            related_signal_ids_json="[]",
        )
        db_session.add(incident)
        await db_session.commit()

        resolved = await manager.reconcile_open_incidents(
            session=db_session,
            active_anomaly_titles=set(),
            active_forecast_titles=None,
            anomaly_grace_minutes=30,
            forecast_grace_minutes=60,
        )
        await db_session.commit()

        assert len(resolved) == 1
        assert resolved[0].status == "resolved"
        assert resolved[0].end_time is not None
