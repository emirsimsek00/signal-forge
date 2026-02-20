"""Tests for forecasting engine."""

import json
from datetime import datetime, timedelta

import pytest

from backend.forecasting.engine import ForecastEngine
from backend.models.signal import Signal


class TestForecastEngine:
    @pytest.mark.asyncio
    async def test_list_metric_names(self, db_session):
        now = datetime.utcnow()
        for i in range(5):
            db_session.add(
                Signal(
                    source="financial",
                    source_id=f"f-{i}",
                    title=f"MRR point {i}",
                    content="Financial update",
                    timestamp=now - timedelta(hours=5 - i),
                    metadata_json=json.dumps(
                        {"metric_name": "mrr", "value": 100000 + i * 1000}
                    ),
                )
            )
        await db_session.commit()

        engine = ForecastEngine()
        metrics = await engine.list_metric_names(db_session, lookback_hours=24)
        assert "mrr" in metrics

    @pytest.mark.asyncio
    async def test_generate_forecast_with_data(self, db_session):
        now = datetime.utcnow()
        for i in range(8):
            db_session.add(
                Signal(
                    source="financial",
                    source_id=f"f2-{i}",
                    title=f"MRR point {i}",
                    content="Financial update",
                    timestamp=now - timedelta(hours=8 - i),
                    metadata_json=json.dumps(
                        {"metric_name": "mrr", "value": 120000 + i * 750}
                    ),
                )
            )
        await db_session.commit()

        engine = ForecastEngine()
        result = await engine.generate(
            session=db_session,
            metric_name="mrr",
            horizon=6,
            lookback_hours=48,
        )
        assert result.metric_name == "mrr"
        assert len(result.observed_points) >= 8
        assert len(result.predicted_values) == 6
        assert result.method in {"linear_regression", "naive_last_value"}
