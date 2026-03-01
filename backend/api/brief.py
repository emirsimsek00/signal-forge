"""Executive brief generator API."""

from __future__ import annotations

from datetime import timedelta

from backend.utils.time import utc_now
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.incident import Incident
from backend.models.signal import Signal
from backend.api.auth import get_tenant_id

router = APIRouter(prefix="/api/brief", tags=["brief"])

ToneMode = Literal["executive_concise", "technical_detailed", "customer_facing"]


def _format_situation(
    tone: ToneMode,
    total_signals: int,
    avg_risk: float,
    critical_count: int,
    high_count: int,
    active_incidents: int,
    lookback_hours: int,
) -> str:
    if tone == "technical_detailed":
        return (
            f"Analyzed {total_signals} signals over the past {lookback_hours}h. "
            f"Average composite risk is {avg_risk:.3f}. "
            f"Detected {critical_count} critical and {high_count} high-risk signals, "
            f"with {active_incidents} active/investigating incidents."
        )
    if tone == "customer_facing":
        return (
            f"In the last {lookback_hours} hours, we monitored {total_signals} operational signals. "
            f"Current risk remains actively monitored ({avg_risk:.2f} average), "
            f"with {active_incidents} open incidents under review."
        )
    return (
        f"Last {lookback_hours}h: {total_signals} signals analyzed, "
        f"avg risk {avg_risk:.2f}, {critical_count} critical and {high_count} high-risk signals, "
        f"{active_incidents} active incidents."
    )


@router.get("/generate")
async def generate_brief(
    tone: ToneMode = Query(default="executive_concise"),
    lookback_hours: int = Query(default=24, ge=1, le=168),
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate a structured executive brief from recent signal activity."""
    now = utc_now()
    since = now - timedelta(hours=lookback_hours)

    total_signals = (
        await session.execute(
            select(func.count()).select_from(Signal).where(Signal.timestamp >= since)
            .where(Signal.tenant_id == tenant_id)
        )
    ).scalar() or 0

    avg_risk = (
        await session.execute(
            select(func.avg(Signal.risk_score))
            .where(Signal.timestamp >= since)
            .where(Signal.tenant_id == tenant_id)
            .where(Signal.risk_score.isnot(None))
        )
    ).scalar() or 0.0

    tier_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    tier_result = await session.execute(
        select(Signal.risk_tier, func.count().label("count"))
        .where(Signal.timestamp >= since)
        .where(Signal.tenant_id == tenant_id)
        .where(Signal.risk_tier.isnot(None))
        .group_by(Signal.risk_tier)
    )
    for tier, count in tier_result.all():
        if tier in tier_counts:
            tier_counts[tier] = int(count)

    sentiment_row = (
        await session.execute(
            select(
                func.count(Signal.id).label("total"),
                func.sum(
                    case((Signal.sentiment_label == "negative", 1), else_=0)
                ).label("negative"),
            )
            .where(Signal.timestamp >= since)
            .where(Signal.tenant_id == tenant_id)
        )
    ).one()
    sentiment_total = int(sentiment_row.total or 0)
    negative_count = int(sentiment_row.negative or 0)
    negative_ratio = (negative_count / sentiment_total) if sentiment_total else 0.0

    source_result = await session.execute(
        select(Signal.source, func.count().label("count"))
        .where(Signal.timestamp >= since)
        .where(Signal.tenant_id == tenant_id)
        .group_by(Signal.source)
        .order_by(desc("count"))
        .limit(5)
    )
    source_distribution = [
        {"source": source, "count": int(count)} for source, count in source_result.all()
    ]

    active_incidents = (
        await session.execute(
            select(func.count())
            .select_from(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.status.in_(["active", "investigating"]))
        )
    ).scalar() or 0

    top_risks_result = await session.execute(
        select(Signal.id, Signal.source, Signal.title, Signal.risk_score, Signal.risk_tier)
        .where(Signal.timestamp >= since)
        .where(Signal.tenant_id == tenant_id)
        .where(Signal.risk_score.isnot(None))
        .order_by(desc(Signal.risk_score))
        .limit(5)
    )
    top_risks = [
        {
            "id": row.id,
            "source": row.source,
            "title": row.title or "Untitled signal",
            "risk_score": round(float(row.risk_score or 0), 3),
            "risk_tier": row.risk_tier or "low",
        }
        for row in top_risks_result
    ]

    top_source = source_distribution[0]["source"] if source_distribution else None
    key_risk_indicators: list[str] = []
    if tier_counts["critical"]:
        key_risk_indicators.append(
            f"{tier_counts['critical']} critical-tier signals detected."
        )
    if tier_counts["high"]:
        key_risk_indicators.append(
            f"{tier_counts['high']} high-tier signals require monitoring."
        )
    if negative_ratio >= 0.45:
        key_risk_indicators.append(
            f"Negative sentiment elevated at {negative_ratio:.0%}."
        )
    if top_source:
        key_risk_indicators.append(
            f"Highest signal volume came from {top_source}."
        )
    if active_incidents:
        key_risk_indicators.append(f"{active_incidents} incidents are currently open.")

    root_cause_hypotheses: list[str] = []
    has_system_risk = any(r["source"] == "system" and r["risk_score"] >= 0.5 for r in top_risks)
    has_support_risk = any(r["source"] == "zendesk" and r["risk_score"] >= 0.5 for r in top_risks)
    has_financial_risk = any(r["source"] == "financial" and r["risk_score"] >= 0.5 for r in top_risks)
    has_social_risk = any(r["source"] == "reddit" and r["risk_score"] >= 0.5 for r in top_risks)

    if has_system_risk and has_support_risk:
        root_cause_hypotheses.append(
            "System degradation may be driving customer-impact ticket pressure."
        )
    if has_system_risk and has_financial_risk:
        root_cause_hypotheses.append(
            "Operational instability may be contributing to revenue-side deviation."
        )
    if has_social_risk and negative_ratio >= 0.45:
        root_cause_hypotheses.append(
            "Public sentiment deterioration may be amplifying incident visibility."
        )
    if not root_cause_hypotheses:
        root_cause_hypotheses.append(
            "No single dominant root cause; risk appears distributed across sources."
        )

    recommended_actions: list[str] = []
    if tier_counts["critical"]:
        recommended_actions.append("Trigger priority incident triage for critical signals.")
    if tier_counts["high"] > 3:
        recommended_actions.append("Run cross-signal correlation on top high-risk events.")
    if negative_ratio >= 0.45:
        recommended_actions.append("Prepare proactive comms for sentiment-sensitive stakeholders.")
    recommended_actions.append("Review source-level thresholds to reduce false positives.")
    recommended_actions.append("Re-evaluate risk weight configuration after incident closure.")

    scored_signals = sum(tier_counts.values())
    coverage = (scored_signals / total_signals) if total_signals else 0.0
    confidence_score = min(
        0.95,
        max(0.45, 0.45 + (coverage * 0.35) + (min(total_signals, 500) / 500 * 0.15)),
    )

    return {
        "generated_at": now.isoformat(),
        "tone": tone,
        "lookback_hours": lookback_hours,
        "situation_overview": _format_situation(
            tone=tone,
            total_signals=int(total_signals),
            avg_risk=float(avg_risk),
            critical_count=tier_counts["critical"],
            high_count=tier_counts["high"],
            active_incidents=int(active_incidents),
            lookback_hours=lookback_hours,
        ),
        "key_risk_indicators": key_risk_indicators,
        "root_cause_hypotheses": root_cause_hypotheses,
        "recommended_actions": recommended_actions,
        "confidence_score": round(confidence_score, 3),
        "supporting_metrics": {
            "total_signals": int(total_signals),
            "avg_risk_score": round(float(avg_risk), 3),
            "tier_distribution": tier_counts,
            "negative_sentiment_ratio": round(negative_ratio, 3),
            "active_incidents": int(active_incidents),
            "source_distribution": source_distribution,
        },
        "top_risk_signals": top_risks,
    }
