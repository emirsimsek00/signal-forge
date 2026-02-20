"""Signal API endpoints — CRUD and ingestion triggers."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.models.signal import Signal, SignalResponse, SignalListResponse
from backend.models.risk import RiskAssessment
from backend.ingestion.manager import IngestionManager
from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer

router = APIRouter(prefix="/api/signals", tags=["signals"])

ingestion_mgr = IngestionManager()
nlp_pipeline = NLPPipeline(use_mock=settings.use_mock_ml)
risk_scorer = RiskScorer()


@router.get("", response_model=SignalListResponse)
async def list_signals(
    source: str | None = Query(None),
    risk_tier: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List signals with optional filtering."""
    query = select(Signal).order_by(desc(Signal.timestamp))

    if source:
        query = query.where(Signal.source == source)
    if risk_tier:
        query = query.where(Signal.risk_tier == risk_tier)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    signals = result.scalars().all()

    return SignalListResponse(
        signals=[SignalResponse.model_validate(s) for s in signals],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single signal by ID."""
    result = await session.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Signal not found")
    return SignalResponse.model_validate(signal)


@router.post("/ingest")
async def trigger_ingestion(
    count: int = Query(30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Trigger signal ingestion, NLP processing, and risk scoring."""
    # 1. Ingest
    new_signals = await ingestion_mgr.ingest_all(session, limit=count)

    # 2. Process through NLP pipeline & score risk
    processed_count = 0
    for sig in new_signals:
        try:
            processed = nlp_pipeline.process(sig.content)

            sig.sentiment_score = processed.sentiment.raw_score
            sig.sentiment_label = processed.sentiment.label
            sig.summary = processed.summary
            sig.entities_json = json.dumps([
                {"text": e.text, "label": e.label} for e in processed.entities
            ])
            # Keep full embedding for correlation + similarity search.
            sig.embedding_json = json.dumps(processed.embedding)
            nlp_pipeline.add_to_index(sig.id, processed.embedding)

            # Parse metadata for risk context
            metadata = {}
            if sig.metadata_json:
                try:
                    metadata = json.loads(sig.metadata_json)
                except json.JSONDecodeError:
                    metadata = {}

            # 3. Risk scoring
            risk = risk_scorer.score(
                sentiment_score=processed.sentiment.raw_score,
                source=sig.source,
                metadata=metadata,
            )
            sig.risk_score = risk.composite_score
            sig.risk_tier = risk.tier

            session.add(
                RiskAssessment(
                    signal_id=sig.id,
                    composite_score=risk.composite_score,
                    sentiment_component=risk.sentiment_component,
                    anomaly_component=risk.anomaly_component,
                    ticket_volume_component=risk.ticket_volume_component,
                    revenue_component=risk.revenue_component,
                    engagement_component=risk.engagement_component,
                    tier=risk.tier,
                    explanation=risk.explanation,
                )
            )

            processed_count += 1
        except Exception as e:
            print(f"[Signals API] Error processing signal {sig.id}: {e}")

    await session.commit()

    return {
        "status": "success",
        "ingested": len(new_signals),
        "processed": processed_count,
        "message": f"Ingested {len(new_signals)} signals, processed {processed_count} through NLP + risk scoring.",
    }


@router.get("/{signal_id}/explain")
async def explain_signal_risk(
    signal_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return the full risk explanation for a signal.

    Includes:
    - Risk component breakdown (sentiment, anomaly, ticket, revenue, engagement)
    - Weight configuration used
    - Contributing signals (FAISS similarity)
    - Timeline of related signals
    """
    from fastapi import HTTPException

    # Get the signal
    result = await session.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Get risk assessment
    risk_result = await session.execute(
        select(RiskAssessment)
        .where(RiskAssessment.signal_id == signal_id)
        .order_by(desc(RiskAssessment.created_at))
        .limit(1)
    )
    risk = risk_result.scalar_one_or_none()

    # Find similar signals via FAISS
    similar_signals = []
    if signal.embedding_json:
        try:
            embedding = json.loads(signal.embedding_json)
            similar_ids = nlp_pipeline.find_similar(embedding, k=6)
            # Get signal details for similar ones (exclude self)
            for sim_id, sim_score in similar_ids:
                if sim_id == signal_id:
                    continue
                sim_result = await session.execute(select(Signal).where(Signal.id == sim_id))
                sim_signal = sim_result.scalar_one_or_none()
                if sim_signal:
                    similar_signals.append({
                        "id": sim_signal.id,
                        "title": sim_signal.title,
                        "source": sim_signal.source,
                        "risk_tier": sim_signal.risk_tier,
                        "risk_score": sim_signal.risk_score,
                        "similarity": round(sim_score, 3),
                        "timestamp": sim_signal.timestamp.isoformat() if sim_signal.timestamp else None,
                    })
        except (json.JSONDecodeError, Exception):
            pass

    # Build component breakdown
    components = {}
    weights = {
        "sentiment": settings.risk_weight_sentiment,
        "anomaly": settings.risk_weight_anomaly,
        "ticket_volume": settings.risk_weight_ticket_volume,
        "revenue": settings.risk_weight_revenue,
        "engagement": settings.risk_weight_engagement,
    }
    if risk:
        components = {
            "sentiment": {"score": risk.sentiment_component, "weight": weights["sentiment"],
                          "weighted": round(risk.sentiment_component * weights["sentiment"], 3)},
            "anomaly": {"score": risk.anomaly_component, "weight": weights["anomaly"],
                        "weighted": round(risk.anomaly_component * weights["anomaly"], 3)},
            "ticket_volume": {"score": risk.ticket_volume_component, "weight": weights["ticket_volume"],
                              "weighted": round(risk.ticket_volume_component * weights["ticket_volume"], 3)},
            "revenue": {"score": risk.revenue_component, "weight": weights["revenue"],
                        "weighted": round(risk.revenue_component * weights["revenue"], 3)},
            "engagement": {"score": risk.engagement_component, "weight": weights["engagement"],
                           "weighted": round(risk.engagement_component * weights["engagement"], 3)},
        }

    # Parse entities
    entities = []
    if signal.entities_json:
        try:
            entities = json.loads(signal.entities_json)
        except json.JSONDecodeError:
            pass

    return {
        "signal": {
            "id": signal.id,
            "source": signal.source,
            "title": signal.title,
            "content": signal.content,
            "timestamp": signal.timestamp.isoformat() if signal.timestamp else None,
            "sentiment_score": signal.sentiment_score,
            "sentiment_label": signal.sentiment_label,
            "summary": signal.summary,
            "risk_score": signal.risk_score,
            "risk_tier": signal.risk_tier,
        },
        "risk_explanation": {
            "composite_score": risk.composite_score if risk else signal.risk_score,
            "tier": risk.tier if risk else signal.risk_tier,
            "explanation": risk.explanation if risk else "No risk assessment available.",
            "components": components,
            "weights": weights,
        },
        "entities": entities,
        "similar_signals": similar_signals,
    }

