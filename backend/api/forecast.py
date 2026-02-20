"""Forecast API — time-series projections for operational metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.forecasting.engine import ForecastEngine

router = APIRouter(prefix="/api/forecast", tags=["forecast"])
engine = ForecastEngine()


@router.get("")
async def get_forecast(
    metric_name: str = Query(default="mrr", min_length=1, max_length=120),
    horizon: int = Query(default=8, ge=1, le=72),
    lookback_hours: int = Query(default=168, ge=6, le=24 * 60),
    session: AsyncSession = Depends(get_session),
):
    """Forecast a metric using recent time-series signals."""
    result = await engine.generate(
        session=session,
        metric_name=metric_name,
        horizon=horizon,
        lookback_hours=lookback_hours,
    )
    return {
        "metric_name": result.metric_name,
        "method": result.method,
        "trend": result.trend,
        "confidence": result.confidence,
        "generated_at": result.generated_at.isoformat(),
        "observed_points": [
            {"timestamp": p.timestamp.isoformat(), "value": round(p.value, 4)}
            for p in result.observed_points
        ],
        "predicted_values": [
            {"timestamp": p.timestamp.isoformat(), "value": round(p.value, 4)}
            for p in result.predicted_values
        ],
    }


@router.get("/metrics")
async def list_forecast_metrics(
    lookback_hours: int = Query(default=168, ge=6, le=24 * 60),
    session: AsyncSession = Depends(get_session),
):
    """List available metric names that can be forecasted."""
    metrics = await engine.list_metric_names(
        session=session,
        lookback_hours=lookback_hours,
    )
    return {"metrics": metrics, "count": len(metrics)}
