"""Signal correlator — discovers relationships between signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.signal import Signal
from backend.nlp.pipeline import NLPPipeline


@dataclass
class CorrelationResult:
    """A single correlation between two signals."""
    signal_id: int
    related_signal_id: int
    score: float  # 0.0 to 1.0
    method: str  # "embedding", "temporal", "entity"
    explanation: str


class SignalCorrelator:
    """Finds related signals using multiple correlation strategies.

    Strategies:
    1. Embedding similarity (FAISS cosine search)
    2. Temporal proximity (same time window)
    3. Entity co-occurrence (shared named entities)
    """

    def __init__(self, pipeline: NLPPipeline) -> None:
        self.pipeline = pipeline

    async def correlate(
        self,
        signal_id: int,
        session: AsyncSession,
        k: int = 10,
        time_window_hours: int = 6,
    ) -> list[CorrelationResult]:
        """Find all correlated signals for a given signal."""
        # Fetch the target signal
        stmt = select(Signal).where(Signal.id == signal_id)
        result = await session.execute(stmt)
        target = result.scalar_one_or_none()
        if not target:
            return []

        correlations: dict[int, CorrelationResult] = {}

        # Strategy 1: Embedding similarity
        if target.embedding_json:
            import json
            embedding = json.loads(target.embedding_json)
            similar = self.pipeline.find_similar(embedding, k=k + 1)
            for related_id, sim_score in similar:
                if related_id == signal_id:
                    continue
                correlations[related_id] = CorrelationResult(
                    signal_id=signal_id,
                    related_signal_id=related_id,
                    score=max(0.0, min(1.0, sim_score)),
                    method="embedding",
                    explanation=f"Semantic similarity: {sim_score:.2%}",
                )

        # Strategy 2: Temporal proximity
        if target.timestamp:
            window_start = target.timestamp - timedelta(hours=time_window_hours)
            window_end = target.timestamp + timedelta(hours=time_window_hours)
            stmt = (
                select(Signal)
                .where(
                    Signal.id != signal_id,
                    Signal.timestamp >= window_start,
                    Signal.timestamp <= window_end,
                    Signal.source != target.source,  # cross-source is more interesting
                )
                .order_by(Signal.timestamp.desc())
                .limit(k)
            )
            result = await session.execute(stmt)
            temporal_signals = result.scalars().all()

            for sig in temporal_signals:
                time_diff = abs((sig.timestamp - target.timestamp).total_seconds())
                max_seconds = time_window_hours * 3600
                temporal_score = 1.0 - (time_diff / max_seconds)

                if sig.id in correlations:
                    # Boost existing correlation
                    existing = correlations[sig.id]
                    existing.score = min(1.0, existing.score + temporal_score * 0.3)
                    existing.method = f"{existing.method}+temporal"
                    existing.explanation += f" | Temporal proximity: {time_diff/60:.0f}min apart"
                else:
                    correlations[sig.id] = CorrelationResult(
                        signal_id=signal_id,
                        related_signal_id=sig.id,
                        score=temporal_score * 0.5,
                        method="temporal",
                        explanation=f"Temporal proximity: {time_diff/60:.0f}min apart, cross-source ({target.source}→{sig.source})",
                    )

        # Strategy 3: Entity co-occurrence
        if target.entities_json:
            import json
            try:
                target_entities = json.loads(target.entities_json)
                target_entity_texts = {e.get("text", "").lower() for e in target_entities if isinstance(e, dict)}

                if target_entity_texts:
                    stmt = (
                        select(Signal)
                        .where(Signal.id != signal_id, Signal.entities_json.isnot(None))
                        .order_by(Signal.timestamp.desc())
                        .limit(100)
                    )
                    result = await session.execute(stmt)
                    candidates = result.scalars().all()

                    for sig in candidates:
                        try:
                            sig_entities = json.loads(sig.entities_json) if sig.entities_json else []
                            sig_entity_texts = {e.get("text", "").lower() for e in sig_entities if isinstance(e, dict)}
                            shared = target_entity_texts & sig_entity_texts
                            if shared:
                                entity_score = min(1.0, len(shared) / max(len(target_entity_texts), 1))
                                if sig.id in correlations:
                                    existing = correlations[sig.id]
                                    existing.score = min(1.0, existing.score + entity_score * 0.2)
                                    existing.method = f"{existing.method}+entity"
                                    existing.explanation += f" | Shared entities: {', '.join(list(shared)[:3])}"
                                else:
                                    correlations[sig.id] = CorrelationResult(
                                        signal_id=signal_id,
                                        related_signal_id=sig.id,
                                        score=entity_score * 0.4,
                                        method="entity",
                                        explanation=f"Shared entities: {', '.join(list(shared)[:3])}",
                                    )
                        except (json.JSONDecodeError, TypeError):
                            continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Sort by score descending, limit to top k
        sorted_results = sorted(correlations.values(), key=lambda c: c.score, reverse=True)
        return sorted_results[:k]
