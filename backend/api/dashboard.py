"""Risk and dashboard data API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.signal import Signal
from backend.models.incident import Incident
from backend.models.risk import RiskOverview, RiskHeatmapCell

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/overview")
async def dashboard_overview(
    session: AsyncSession = Depends(get_session),
):
    """Aggregated dashboard overview — KPI cards data."""
    # Total signals
    total_signals = (
        await session.execute(select(func.count()).select_from(Signal))
    ).scalar() or 0

    # Active incidents
    active_incidents = (
        await session.execute(
            select(func.count()).select_from(Incident).where(
                Incident.status.in_(["active", "investigating"])
            )
        )
    ).scalar() or 0

    # Average risk score
    avg_risk = (
        await session.execute(
            select(func.avg(Signal.risk_score)).where(Signal.risk_score.isnot(None))
        )
    ).scalar() or 0.0

    # Risk tier distribution
    tier_counts = {}
    for tier in ["critical", "high", "moderate", "low"]:
        count = (
            await session.execute(
                select(func.count()).select_from(Signal).where(Signal.risk_tier == tier)
            )
        ).scalar() or 0
        tier_counts[tier] = count

    # Source distribution
    source_query = (
        select(Signal.source, func.count().label("count"))
        .group_by(Signal.source)
        .order_by(desc("count"))
    )
    source_result = await session.execute(source_query)
    source_distribution = [
        {"source": row[0], "count": row[1]}
        for row in source_result.all()
    ]

    # Recent signals (last 10)
    recent = await session.execute(
        select(Signal).order_by(desc(Signal.timestamp)).limit(10)
    )
    recent_signals = [
        {
            "id": s.id,
            "source": s.source,
            "title": s.title or s.content[:80],
            "risk_score": s.risk_score,
            "risk_tier": s.risk_tier,
            "sentiment_label": s.sentiment_label,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        }
        for s in recent.scalars().all()
    ]

    # Signals per hour (last 24h)
    signals_per_hour = []
    now = datetime.utcnow()
    for hours_ago in range(24, 0, -1):
        start = now - timedelta(hours=hours_ago)
        end = now - timedelta(hours=hours_ago - 1)
        count = (
            await session.execute(
                select(func.count())
                .select_from(Signal)
                .where(Signal.timestamp >= start, Signal.timestamp < end)
            )
        ).scalar() or 0
        signals_per_hour.append({
            "hour": start.strftime("%H:00"),
            "count": count,
        })

    return {
        "total_signals": total_signals,
        "active_incidents": active_incidents,
        "avg_risk_score": round(avg_risk, 3),
        "tier_distribution": tier_counts,
        "source_distribution": source_distribution,
        "recent_signals": recent_signals,
        "signals_per_hour": signals_per_hour,
    }


@router.get("/risk/overview")
async def risk_overview(
    session: AsyncSession = Depends(get_session),
):
    """Risk scoring overview data."""
    avg_score = (
        await session.execute(
            select(func.avg(Signal.risk_score)).where(Signal.risk_score.isnot(None))
        )
    ).scalar() or 0.0

    tier_counts = {}
    for tier in ["critical", "high", "moderate", "low"]:
        tier_counts[tier] = (
            await session.execute(
                select(func.count()).select_from(Signal).where(Signal.risk_tier == tier)
            )
        ).scalar() or 0

    total_signals = sum(tier_counts.values())

    # Top risk signals
    top_risk = await session.execute(
        select(Signal)
        .where(Signal.risk_score.isnot(None))
        .order_by(desc(Signal.risk_score))
        .limit(10)
    )
    top_risks = [
        {
            "id": s.id,
            "source": s.source,
            "title": s.title or s.content[:80],
            "risk_score": s.risk_score,
            "risk_tier": s.risk_tier,
            "sentiment_label": s.sentiment_label,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        }
        for s in top_risk.scalars().all()
    ]

    return {
        "average_score": round(avg_score, 3),
        "critical_count": tier_counts["critical"],
        "high_count": tier_counts["high"],
        "moderate_count": tier_counts["moderate"],
        "low_count": tier_counts["low"],
        "total_signals": total_signals,
        "trend": "stable",
        "top_risks": top_risks,
    }


@router.get("/risk/heatmap")
async def risk_heatmap(
    session: AsyncSession = Depends(get_session),
):
    """Risk heatmap data — source × hour matrix."""
    signals_result = await session.execute(
        select(Signal)
        .where(Signal.risk_score.isnot(None))
        .order_by(Signal.timestamp)
    )
    signals = signals_result.scalars().all()

    # Build heatmap grid
    heatmap: dict[tuple[str, int], list[float]] = defaultdict(list)
    for s in signals:
        hour = s.timestamp.hour if s.timestamp else 0
        heatmap[(s.source, hour)].append(s.risk_score or 0)

    cells = []
    for (source, hour), scores in heatmap.items():
        avg_score = sum(scores) / len(scores)
        tier = "critical" if avg_score >= 0.75 else "high" if avg_score >= 0.5 else "moderate" if avg_score >= 0.25 else "low"
        cells.append({
            "source": source,
            "hour": hour,
            "score": round(avg_score, 3),
            "tier": tier,
            "count": len(scores),
        })

    return {"cells": cells}


@router.get("/dashboard/timeline")
async def dashboard_timeline(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Combined timeline of signals and incidents ordered by time."""
    signals_result = await session.execute(
        select(Signal).order_by(desc(Signal.timestamp)).limit(limit)
    )
    signals = signals_result.scalars().all()

    incidents_result = await session.execute(
        select(Incident).order_by(desc(Incident.start_time)).limit(limit)
    )
    incidents = incidents_result.scalars().all()

    timeline = []
    for s in signals:
        timeline.append({
            "type": "signal",
            "id": s.id,
            "source": s.source,
            "title": s.title or s.content[:80],
            "risk_tier": s.risk_tier,
            "risk_score": s.risk_score,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        })
    for i in incidents:
        timeline.append({
            "type": "incident",
            "id": i.id,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "timestamp": i.start_time.isoformat() if i.start_time else None,
        })

    timeline.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return {"timeline": timeline[:limit]}
