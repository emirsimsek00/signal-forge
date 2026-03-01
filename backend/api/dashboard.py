"""Risk and dashboard data API endpoints."""

from __future__ import annotations

from datetime import timedelta

from backend.utils.time import utc_now

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, cast, Integer, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.signal import Signal
from backend.models.incident import Incident
from backend.api.auth import get_required_tenant_id

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/overview")
async def dashboard_overview(
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Aggregated dashboard overview — KPI cards data."""
    now = utc_now()

    # Total signals
    total_signals = (
        await session.execute(select(func.count()).select_from(Signal).where(Signal.tenant_id == tenant_id))
    ).scalar() or 0

    # Active incidents
    active_incidents = (
        await session.execute(
            select(func.count()).select_from(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.status.in_(["active", "investigating"])
            )
        )
    ).scalar() or 0

    # Average risk score
    avg_risk = (
        await session.execute(
            select(func.avg(Signal.risk_score)).where(Signal.tenant_id == tenant_id, Signal.risk_score.isnot(None))
        )
    ).scalar() or 0.0

    # Risk tier distribution (single grouped query)
    tier_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    tier_result = await session.execute(
        select(Signal.risk_tier, func.count().label("count"))
        .where(Signal.tenant_id == tenant_id, Signal.risk_tier.isnot(None))
        .group_by(Signal.risk_tier)
    )
    for tier, count in tier_result.all():
        if tier in tier_counts:
            tier_counts[tier] = int(count)

    # Source distribution
    source_query = (
        select(Signal.source, func.count().label("count"))
        .where(Signal.tenant_id == tenant_id)
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
        select(Signal)
        .where(Signal.tenant_id == tenant_id)
        .order_by(desc(Signal.timestamp))
        .limit(10)
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

    # Signals per hour (last 24h) via grouped query
    window_start = now - timedelta(hours=24)
    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    if dialect_name == "sqlite":
        hour_bucket_expr = func.strftime("%Y-%m-%d %H:00:00", Signal.timestamp)
    else:
        hour_bucket_expr = func.date_trunc("hour", Signal.timestamp)

    hourly_result = await session.execute(
        select(
            hour_bucket_expr.label("hour_bucket"),
            func.count().label("count"),
        )
        .where(Signal.tenant_id == tenant_id, Signal.timestamp >= window_start)
        .group_by("hour_bucket")
        .order_by("hour_bucket")
    )

    hourly_counts: dict[str, int] = {}
    for bucket, count in hourly_result.all():
        if bucket is None:
            continue
        if isinstance(bucket, str):
            key = bucket[:13]  # YYYY-MM-DD HH
        else:
            key = bucket.strftime("%Y-%m-%d %H")
        hourly_counts[key] = int(count)

    signals_per_hour = []
    for hours_ago in range(23, -1, -1):
        hour_start = (now - timedelta(hours=hours_ago)).replace(
            minute=0, second=0, microsecond=0
        )
        key = hour_start.strftime("%Y-%m-%d %H")
        signals_per_hour.append(
            {
                "hour": hour_start.strftime("%H:00"),
                "count": hourly_counts.get(key, 0),
            }
        )

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
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Risk scoring overview data."""
    avg_score = (
        await session.execute(
            select(func.avg(Signal.risk_score)).where(
                Signal.tenant_id == tenant_id,
                Signal.risk_score.isnot(None),
            )
        )
    ).scalar() or 0.0

    tier_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    tier_result = await session.execute(
        select(Signal.risk_tier, func.count().label("count"))
        .where(Signal.tenant_id == tenant_id, Signal.risk_tier.isnot(None))
        .group_by(Signal.risk_tier)
    )
    for tier, count in tier_result.all():
        if tier in tier_counts:
            tier_counts[tier] = int(count)

    total_signals = sum(tier_counts.values())

    # Top risk signals
    top_risk = await session.execute(
        select(Signal)
        .where(Signal.tenant_id == tenant_id, Signal.risk_score.isnot(None))
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
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Risk heatmap data — source × hour matrix."""
    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    if dialect_name == "sqlite":
        hour_expr = cast(func.strftime("%H", Signal.timestamp), Integer)
    else:
        hour_expr = cast(func.extract("hour", Signal.timestamp), Integer)

    aggregated = await session.execute(
        select(
            Signal.source.label("source"),
            hour_expr.label("hour"),
            func.avg(Signal.risk_score).label("avg_score"),
            func.count().label("count"),
        )
        .where(Signal.tenant_id == tenant_id, Signal.risk_score.isnot(None))
        .group_by("source", "hour")
        .order_by("source", "hour")
    )

    cells = []
    for row in aggregated.all():
        avg_score = float(row.avg_score or 0)
        tier = (
            "critical" if avg_score >= 0.75
            else "high" if avg_score >= 0.5
            else "moderate" if avg_score >= 0.25
            else "low"
        )
        cells.append(
            {
                "source": row.source,
                "hour": int(row.hour or 0),
                "score": round(avg_score, 3),
                "tier": tier,
                "count": int(row.count or 0),
            }
        )

    return {"cells": cells}


@router.get("/dashboard/timeline")
async def dashboard_timeline(
    limit: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Combined timeline of signals and incidents ordered by time."""
    signals_result = await session.execute(
        select(Signal)
        .where(Signal.tenant_id == tenant_id)
        .order_by(desc(Signal.timestamp))
        .limit(limit)
    )
    signals = signals_result.scalars().all()

    incidents_result = await session.execute(
        select(Incident)
        .where(Incident.tenant_id == tenant_id)
        .order_by(desc(Incident.start_time))
        .limit(limit)
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


@router.get("/dashboard/risk-trend")
async def risk_trend(
    hours: int = Query(72, ge=6, le=168),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Risk score trend over time — hourly averages with tier counts."""
    now = utc_now()
    window_start = now - timedelta(hours=hours)

    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    if dialect_name == "sqlite":
        hour_bucket_expr = func.strftime("%Y-%m-%d %H:00:00", Signal.timestamp)
    else:
        hour_bucket_expr = func.date_trunc("hour", Signal.timestamp)

    result = await session.execute(
        select(
            hour_bucket_expr.label("bucket"),
            func.avg(Signal.risk_score).label("avg_risk"),
            func.max(Signal.risk_score).label("max_risk"),
            func.count().label("count"),
            func.sum(
                case(
                    (Signal.risk_tier.in_(["critical", "high"]), 1),
                    else_=0,
                )
            ).label("high_risk_count"),
        )
        .where(
            Signal.tenant_id == tenant_id,
            Signal.timestamp >= window_start,
            Signal.risk_score.isnot(None),
        )
        .group_by("bucket")
        .order_by("bucket")
    )

    points = []
    for row in result.all():
        if row.bucket is None:
            continue
        ts = row.bucket if isinstance(row.bucket, str) else row.bucket.isoformat()
        points.append({
            "timestamp": ts,
            "avg_risk": round(float(row.avg_risk or 0), 4),
            "max_risk": round(float(row.max_risk or 0), 4),
            "count": int(row.count or 0),
            "high_risk_count": int(row.high_risk_count or 0),
        })

    return {"hours": hours, "points": points}


@router.get("/dashboard/sentiment-drift")
async def sentiment_drift(
    hours: int = Query(72, ge=6, le=168),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Sentiment trend over time — average sentiment and label distribution."""
    now = utc_now()
    window_start = now - timedelta(hours=hours)

    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    if dialect_name == "sqlite":
        hour_bucket_expr = func.strftime("%Y-%m-%d %H:00:00", Signal.timestamp)
    else:
        hour_bucket_expr = func.date_trunc("hour", Signal.timestamp)

    result = await session.execute(
        select(
            hour_bucket_expr.label("bucket"),
            func.avg(Signal.sentiment_score).label("avg_sentiment"),
            func.count().label("total"),
            func.sum(case((Signal.sentiment_label == "negative", 1), else_=0)).label("negative"),
            func.sum(case((Signal.sentiment_label == "positive", 1), else_=0)).label("positive"),
            func.sum(case((Signal.sentiment_label == "neutral", 1), else_=0)).label("neutral"),
        )
        .where(
            Signal.tenant_id == tenant_id,
            Signal.timestamp >= window_start,
            Signal.sentiment_score.isnot(None),
        )
        .group_by("bucket")
        .order_by("bucket")
    )

    points = []
    for row in result.all():
        if row.bucket is None:
            continue
        ts = row.bucket if isinstance(row.bucket, str) else row.bucket.isoformat()
        total = int(row.total or 1)
        points.append({
            "timestamp": ts,
            "avg_sentiment": round(float(row.avg_sentiment or 0), 4),
            "negative_ratio": round(int(row.negative or 0) / total, 3),
            "positive_ratio": round(int(row.positive or 0) / total, 3),
            "neutral_ratio": round(int(row.neutral or 0) / total, 3),
            "total": total,
        })

    return {"hours": hours, "points": points}


@router.get("/dashboard/incident-frequency")
async def incident_frequency(
    days: int = Query(14, ge=1, le=90),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Daily incident creation frequency with severity breakdown."""
    now = utc_now()
    window_start = now - timedelta(days=days)

    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    if dialect_name == "sqlite":
        day_bucket_expr = func.strftime("%Y-%m-%d", Incident.created_at)
    else:
        day_bucket_expr = func.date_trunc("day", Incident.created_at)

    result = await session.execute(
        select(
            day_bucket_expr.label("bucket"),
            func.count().label("total"),
            func.sum(case((Incident.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Incident.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((Incident.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((Incident.severity == "low", 1), else_=0)).label("low"),
        )
        .where(Incident.tenant_id == tenant_id, Incident.created_at >= window_start)
        .group_by("bucket")
        .order_by("bucket")
    )

    points = []
    for row in result.all():
        if row.bucket is None:
            continue
        ts = row.bucket if isinstance(row.bucket, str) else row.bucket.strftime("%Y-%m-%d")
        points.append({
            "date": ts,
            "total": int(row.total or 0),
            "critical": int(row.critical or 0),
            "high": int(row.high or 0),
            "medium": int(row.medium or 0),
            "low": int(row.low or 0),
        })

    return {"days": days, "points": points}
