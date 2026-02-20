"""Scenario simulator API — 'What if' analysis for risk impact."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.models.signal import Signal

logger = logging.getLogger("signalforge.simulator")
router = APIRouter(prefix="/api/simulator", tags=["simulator"])


class ScenarioRequest(BaseModel):
    """What-if scenario parameters."""
    sentiment_shift: float = 0.0      # e.g., -0.1 means 10% more negative
    volume_multiplier: float = 1.0    # e.g., 2.0 means double the signals
    risk_weight_sentiment: float | None = None
    risk_weight_anomaly: float | None = None
    risk_weight_ticket_volume: float | None = None
    risk_weight_revenue: float | None = None
    risk_weight_engagement: float | None = None


class ScenarioResult(BaseModel):
    baseline_avg_risk: float
    projected_avg_risk: float
    delta: float
    baseline_tier_distribution: dict[str, int]
    projected_tier_distribution: dict[str, int]
    signals_analyzed: int
    high_risk_change: int  # how many signals move to high/critical


@router.post("/run", response_model=ScenarioResult)
async def run_scenario(
    request: ScenarioRequest,
    session: AsyncSession = Depends(get_session),
):
    """Simulate risk impact of 'what if' scenario changes.

    Applies the user's parameter shifts to the existing signal dataset
    and recalculates projected risk scores.
    """
    from backend.risk.scorer import RiskScorer

    # Get current signal data
    result = await session.execute(
        select(Signal).where(Signal.risk_score.isnot(None)).limit(200)
    )
    signals = list(result.scalars().all())

    if not signals:
        return ScenarioResult(
            baseline_avg_risk=0,
            projected_avg_risk=0,
            delta=0,
            baseline_tier_distribution={},
            projected_tier_distribution={},
            signals_analyzed=0,
            high_risk_change=0,
        )

    # Calculate baseline
    baseline_scores = [s.risk_score for s in signals if s.risk_score is not None]
    baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0

    baseline_tiers: dict[str, int] = {}
    for s in signals:
        tier = s.risk_tier or "unknown"
        baseline_tiers[tier] = baseline_tiers.get(tier, 0) + 1

    baseline_high = baseline_tiers.get("high", 0) + baseline_tiers.get("critical", 0)

    # Build scenario scorer with modified weights
    scenario_scorer = RiskScorer()
    if request.risk_weight_sentiment is not None:
        scenario_scorer.weights["sentiment"] = request.risk_weight_sentiment
    if request.risk_weight_anomaly is not None:
        scenario_scorer.weights["anomaly"] = request.risk_weight_anomaly
    if request.risk_weight_ticket_volume is not None:
        scenario_scorer.weights["ticket_volume"] = request.risk_weight_ticket_volume
    if request.risk_weight_revenue is not None:
        scenario_scorer.weights["revenue"] = request.risk_weight_revenue
    if request.risk_weight_engagement is not None:
        scenario_scorer.weights["engagement"] = request.risk_weight_engagement

    # Project new scores
    projected_scores: list[float] = []
    projected_tiers: dict[str, int] = {}

    for s in signals:
        shifted_sentiment = (s.sentiment_score or 0) + request.sentiment_shift
        shifted_sentiment = max(-1.0, min(1.0, shifted_sentiment))

        import json
        metadata = {}
        if s.metadata_json:
            try:
                metadata = json.loads(s.metadata_json)
            except Exception:
                pass

        risk = scenario_scorer.score(
            sentiment_score=shifted_sentiment,
            source=s.source,
            metadata=metadata,
        )
        projected_scores.append(risk.composite_score)
        projected_tiers[risk.tier] = projected_tiers.get(risk.tier, 0) + 1

    projected_avg = sum(projected_scores) / len(projected_scores) if projected_scores else 0
    projected_high = projected_tiers.get("high", 0) + projected_tiers.get("critical", 0)

    return ScenarioResult(
        baseline_avg_risk=round(baseline_avg, 4),
        projected_avg_risk=round(projected_avg, 4),
        delta=round(projected_avg - baseline_avg, 4),
        baseline_tier_distribution=baseline_tiers,
        projected_tier_distribution=projected_tiers,
        signals_analyzed=len(signals),
        high_risk_change=projected_high - baseline_high,
    )
