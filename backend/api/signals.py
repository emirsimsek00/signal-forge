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
            sig.embedding_json = json.dumps(processed.embedding[:10])  # Store truncated

            # Parse metadata for risk context
            metadata = json.loads(sig.metadata_json) if sig.metadata_json else {}

            # 3. Risk scoring
            risk = risk_scorer.score(
                sentiment_score=processed.sentiment.raw_score,
                metadata=metadata,
            )
            sig.risk_score = risk.composite_score
            sig.risk_tier = risk.tier

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
