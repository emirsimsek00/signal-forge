"""Anomaly detector — statistical anomaly detection on signals."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.utils.time import utc_now
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.signal import Signal


@dataclass
class AnomalyEvent:
    """Represents a detected anomaly."""
    id: str
    type: str  # "volume_spike", "risk_spike", "sentiment_drift"
    severity: str  # "critical", "high", "moderate"
    title: str
    description: str
    affected_source: Optional[str]
    metric_value: float
    threshold: float
    affected_signal_ids: list[int] = field(default_factory=list)
    detected_at: datetime = field(default_factory=utc_now)


class AnomalyDetector:
    """Detects anomalies in signal patterns using statistical methods."""

    def __init__(self) -> None:
        self._events: list[AnomalyEvent] = []
        self._max_events = 100

    @property
    def recent_events(self) -> list[AnomalyEvent]:
        return list(reversed(self._events[-self._max_events:]))

    async def run_detection(self, session: AsyncSession) -> list[AnomalyEvent]:
        """Run all anomaly detection passes and return new events."""
        new_events: list[AnomalyEvent] = []

        vol_events = await self._detect_volume_spikes(session)
        new_events.extend(vol_events)

        risk_events = await self._detect_risk_spikes(session)
        new_events.extend(risk_events)

        sentiment_events = await self._detect_sentiment_drift(session)
        new_events.extend(sentiment_events)

        self._events.extend(new_events)
        # Trim old events
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        return new_events

    async def _detect_volume_spikes(self, session: AsyncSession) -> list[AnomalyEvent]:
        """Detect unusual signal volume per source in the last hour vs rolling average."""
        events: list[AnomalyEvent] = []
        now = utc_now()

        # Count signals per source in the last hour
        recent_query = (
            select(Signal.source, func.count(Signal.id).label("cnt"))
            .where(Signal.timestamp >= now - timedelta(hours=1))
            .group_by(Signal.source)
        )
        recent_result = await session.execute(recent_query)
        recent_counts = {row.source: row.cnt for row in recent_result}

        # Count signals per source per hour over last 24h for baseline
        baseline_query = (
            select(Signal.source, func.count(Signal.id).label("cnt"))
            .where(Signal.timestamp >= now - timedelta(hours=24))
            .where(Signal.timestamp < now - timedelta(hours=1))
            .group_by(Signal.source)
        )
        baseline_result = await session.execute(baseline_query)
        baseline_counts = {row.source: row.cnt / 23.0 for row in baseline_result}  # 23h average

        for source, recent_count in recent_counts.items():
            baseline_avg = baseline_counts.get(source, 0)
            if baseline_avg < 2:
                continue  # Not enough baseline data

            # Z-score equivalent: how many standard deviations from mean
            std_dev = max(math.sqrt(baseline_avg), 1)  # Approximate Poisson std dev
            z_score = (recent_count - baseline_avg) / std_dev

            if z_score >= 3.0:
                severity = "critical" if z_score >= 5.0 else "high"
                events.append(AnomalyEvent(
                    id=f"vol-{source}-{now.isoformat()[:16]}",
                    type="volume_spike",
                    severity=severity,
                    title=f"Volume spike: {source}",
                    description=(
                        f"{source} source produced {recent_count} signals in the last hour, "
                        f"vs {baseline_avg:.1f}/hr average (z-score: {z_score:.1f})"
                    ),
                    affected_source=source,
                    metric_value=float(recent_count),
                    threshold=baseline_avg + 3 * std_dev,
                ))

        return events

    async def _detect_risk_spikes(self, session: AsyncSession) -> list[AnomalyEvent]:
        """Detect sudden risk score jumps above 2σ from rolling mean."""
        events: list[AnomalyEvent] = []
        now = utc_now()

        # Recent avg risk (last hour)
        recent = await session.execute(
            select(func.avg(Signal.risk_score), func.count(Signal.id))
            .where(Signal.timestamp >= now - timedelta(hours=1))
            .where(Signal.risk_score.isnot(None))
        )
        recent_row = recent.one()
        recent_avg = float(recent_row[0] or 0)
        recent_count = int(recent_row[1] or 0)

        if recent_count < 3:
            return events

        # Baseline avg risk (last 24h excluding last hour)
        baseline = await session.execute(
            select(func.avg(Signal.risk_score), func.count(Signal.id))
            .where(Signal.timestamp >= now - timedelta(hours=24))
            .where(Signal.timestamp < now - timedelta(hours=1))
            .where(Signal.risk_score.isnot(None))
        )
        baseline_row = baseline.one()
        baseline_avg = float(baseline_row[0] or 0)
        baseline_count = int(baseline_row[1] or 0)

        if baseline_count < 5 or baseline_avg == 0:
            return events

        # Check if recent is significantly higher
        ratio = recent_avg / baseline_avg
        if ratio >= 1.5:
            severity = "critical" if ratio >= 2.0 else "high"

            # Find high-risk signals from last hour
            high_risk = await session.execute(
                select(Signal.id)
                .where(Signal.timestamp >= now - timedelta(hours=1))
                .where(Signal.risk_score >= 0.6)
                .order_by(Signal.risk_score.desc())
                .limit(10)
            )
            signal_ids = [row[0] for row in high_risk]

            events.append(AnomalyEvent(
                id=f"risk-{now.isoformat()[:16]}",
                type="risk_spike",
                severity=severity,
                title="Risk score surge detected",
                description=(
                    f"Average risk score jumped to {recent_avg:.1%} (from {baseline_avg:.1%} baseline), "
                    f"a {ratio:.1f}x increase"
                ),
                affected_source=None,
                metric_value=recent_avg,
                threshold=baseline_avg * 1.5,
                affected_signal_ids=signal_ids,
            ))

        return events

    async def _detect_sentiment_drift(self, session: AsyncSession) -> list[AnomalyEvent]:
        """Detect shift from neutral/positive to predominantly negative sentiment."""
        events: list[AnomalyEvent] = []
        now = utc_now()

        # Recent negative ratio (last 2 hours)
        recent = await session.execute(
            select(
                func.count(Signal.id).label("total"),
                func.sum(
                    func.cast(Signal.sentiment_label == "negative", Signal.id.type)
                ).label("neg_count"),
            )
            .where(Signal.timestamp >= now - timedelta(hours=2))
            .where(Signal.sentiment_label.isnot(None))
        )
        recent_row = recent.one()
        recent_total = int(recent_row[0] or 0)
        recent_neg = int(recent_row[1] or 0)

        if recent_total < 5:
            return events

        # Baseline negative ratio (last 24h excluding last 2h)
        baseline = await session.execute(
            select(
                func.count(Signal.id).label("total"),
                func.sum(
                    func.cast(Signal.sentiment_label == "negative", Signal.id.type)
                ).label("neg_count"),
            )
            .where(Signal.timestamp >= now - timedelta(hours=24))
            .where(Signal.timestamp < now - timedelta(hours=2))
            .where(Signal.sentiment_label.isnot(None))
        )
        baseline_row = baseline.one()
        baseline_total = int(baseline_row[0] or 0)
        baseline_neg = int(baseline_row[1] or 0)

        if baseline_total < 5:
            return events

        recent_neg_ratio = recent_neg / recent_total
        baseline_neg_ratio = baseline_neg / baseline_total if baseline_total > 0 else 0

        # Significant shift to negative
        if recent_neg_ratio >= 0.5 and recent_neg_ratio > baseline_neg_ratio * 1.5:
            severity = "critical" if recent_neg_ratio >= 0.75 else "moderate"
            events.append(AnomalyEvent(
                id=f"sent-{now.isoformat()[:16]}",
                type="sentiment_drift",
                severity=severity,
                title="Negative sentiment surge",
                description=(
                    f"{recent_neg_ratio:.0%} of recent signals have negative sentiment "
                    f"(vs {baseline_neg_ratio:.0%} baseline)"
                ),
                affected_source=None,
                metric_value=recent_neg_ratio,
                threshold=baseline_neg_ratio * 1.5,
            ))

        return events


# Singleton instance
detector = AnomalyDetector()
