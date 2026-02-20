"""Time-series forecasting engine for metric signals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.signal import Signal


@dataclass
class ForecastPoint:
    timestamp: datetime
    value: float


@dataclass
class ForecastResult:
    metric_name: str
    method: str
    trend: str
    confidence: float
    observed_points: list[ForecastPoint]
    predicted_values: list[ForecastPoint]
    generated_at: datetime


class ForecastEngine:
    """Simple metric forecasting over signal metadata time series."""

    async def generate(
        self,
        session: AsyncSession,
        metric_name: str,
        horizon: int = 8,
        lookback_hours: int = 168,
    ) -> ForecastResult:
        series = await self._load_metric_series(
            session=session,
            metric_name=metric_name,
            lookback_hours=lookback_hours,
        )
        if not series:
            return ForecastResult(
                metric_name=metric_name,
                method="insufficient_data",
                trend="stable",
                confidence=0.0,
                observed_points=[],
                predicted_values=[],
                generated_at=datetime.utcnow(),
            )

        if len(series) < 3:
            return self._naive_forecast(metric_name=metric_name, series=series, horizon=horizon)
        return self._linear_forecast(metric_name=metric_name, series=series, horizon=horizon)

    async def list_metric_names(
        self,
        session: AsyncSession,
        lookback_hours: int = 168,
        max_scan_rows: int = 3000,
    ) -> list[str]:
        since = datetime.utcnow() - timedelta(hours=lookback_hours)
        result = await session.execute(
            select(Signal.metadata_json)
            .where(Signal.timestamp >= since, Signal.metadata_json.isnot(None))
            .where(Signal.source.in_(["financial", "system"]))
            .order_by(desc(Signal.timestamp))
            .limit(max_scan_rows)
        )

        metric_names: set[str] = set()
        for metadata_json in result.scalars().all():
            if not metadata_json:
                continue
            try:
                metadata = json.loads(metadata_json)
            except (json.JSONDecodeError, TypeError):
                continue
            metric = metadata.get("metric_name")
            value = metadata.get("value")
            if isinstance(metric, str) and metric.strip() and isinstance(value, (int, float)):
                metric_names.add(metric.strip())
        return sorted(metric_names)

    async def _load_metric_series(
        self,
        session: AsyncSession,
        metric_name: str,
        lookback_hours: int,
    ) -> list[ForecastPoint]:
        since = datetime.utcnow() - timedelta(hours=lookback_hours)
        result = await session.execute(
            select(Signal.timestamp, Signal.metadata_json)
            .where(Signal.timestamp >= since, Signal.metadata_json.isnot(None))
            .where(Signal.source.in_(["financial", "system"]))
            .order_by(Signal.timestamp.asc())
            .limit(6000)
        )

        points: list[ForecastPoint] = []
        for ts, metadata_json in result.all():
            if ts is None or not metadata_json:
                continue
            try:
                metadata = json.loads(metadata_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if metadata.get("metric_name") != metric_name:
                continue
            value = metadata.get("value")
            if not isinstance(value, (int, float)):
                continue
            points.append(ForecastPoint(timestamp=ts, value=float(value)))

        # Keep latest points for stability.
        if len(points) > 240:
            return points[-240:]
        return points

    def _naive_forecast(
        self,
        metric_name: str,
        series: list[ForecastPoint],
        horizon: int,
    ) -> ForecastResult:
        last = series[-1]
        step = self._estimate_step(series)
        predicted = [
            ForecastPoint(timestamp=last.timestamp + step * (i + 1), value=last.value)
            for i in range(horizon)
        ]
        return ForecastResult(
            metric_name=metric_name,
            method="naive_last_value",
            trend="stable",
            confidence=0.45,
            observed_points=series,
            predicted_values=predicted,
            generated_at=datetime.utcnow(),
        )

    def _linear_forecast(
        self,
        metric_name: str,
        series: list[ForecastPoint],
        horizon: int,
    ) -> ForecastResult:
        base = series[0].timestamp
        x = np.array(
            [(point.timestamp - base).total_seconds() for point in series],
            dtype=np.float64,
        )
        y = np.array([point.value for point in series], dtype=np.float64)

        slope, intercept = np.polyfit(x, y, 1)
        fitted = slope * x + intercept
        residual = float(np.sqrt(np.mean((y - fitted) ** 2))) if len(y) > 1 else 0.0

        step = self._estimate_step(series)
        next_x = np.array(
            [
                (series[-1].timestamp + step * (i + 1) - base).total_seconds()
                for i in range(horizon)
            ],
            dtype=np.float64,
        )
        next_y = slope * next_x + intercept

        predicted = [
            ForecastPoint(
                timestamp=series[-1].timestamp + step * (i + 1),
                value=float(next_y[i]),
            )
            for i in range(horizon)
        ]

        trend = "rising" if slope > 0 else "falling" if slope < 0 else "stable"
        value_scale = max(float(np.std(y)), 1e-6)
        fit_quality = max(0.0, 1.0 - (residual / (value_scale * 2.0)))
        confidence = min(0.95, max(0.5, 0.5 + fit_quality * 0.4))

        return ForecastResult(
            metric_name=metric_name,
            method="linear_regression",
            trend=trend,
            confidence=round(confidence, 3),
            observed_points=series,
            predicted_values=predicted,
            generated_at=datetime.utcnow(),
        )

    @staticmethod
    def _estimate_step(series: list[ForecastPoint]) -> timedelta:
        if len(series) < 2:
            return timedelta(hours=1)

        deltas = [
            (series[i].timestamp - series[i - 1].timestamp).total_seconds()
            for i in range(1, len(series))
        ]
        positive = [delta for delta in deltas if delta > 0]
        if not positive:
            return timedelta(hours=1)

        median_seconds = float(np.median(np.array(positive, dtype=np.float64)))
        median_seconds = max(60.0, min(median_seconds, 24 * 3600.0))
        return timedelta(seconds=median_seconds)
