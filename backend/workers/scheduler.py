"""Background scheduler — auto-ingests and processes signals on an interval."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from backend.config import settings
from backend.database import async_session, engine
from backend.ingestion.manager import IngestionManager
from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer
from backend.api.websocket import manager as ws_manager


class BackgroundScheduler:
    """Asyncio-based background scheduler for continuous ingestion.

    Runs as a background task inside the FastAPI event loop.
    On each tick:
      1. Ingest signals from all sources
      2. Process through NLP pipeline
      3. Score risk
      4. Broadcast new signals + alerts via WebSocket
    """

    def __init__(self) -> None:
        self.interval = settings.ingestion_interval_seconds
        self.ingestion_manager = IngestionManager()
        self.pipeline = NLPPipeline(use_mock=settings.use_mock_ml)
        self.risk_scorer = RiskScorer()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background scheduler."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        print(f"[Scheduler] Started (interval={self.interval}s)")

    async def stop(self) -> None:
        """Stop the background scheduler gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] Stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                if not self._running:
                    break
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Scheduler] Error in tick: {e}")
                await asyncio.sleep(10)  # back off on error

    async def _tick(self) -> None:
        """Single scheduler tick: ingest → process → score → broadcast."""
        async with async_session() as session:
            # Ingest
            signals = await self.ingestion_manager.ingest_all(session, limit=15)
            if not signals:
                return

            print(f"[Scheduler] Processing {len(signals)} new signals")

            # Process through NLP + Risk
            for sig in signals:
                try:
                    processed = self.pipeline.process(sig.content)

                    sig.sentiment_score = processed.sentiment.raw_score
                    sig.sentiment_label = processed.sentiment.label
                    sig.entities_json = json.dumps(
                        [{"text": e.text, "label": e.label} for e in processed.entities]
                    )
                    sig.summary = processed.summary
                    sig.embedding_json = json.dumps(processed.embedding)

                    # Risk scoring
                    risk = self.risk_scorer.score(
                        sentiment_score=processed.sentiment.raw_score,
                        metadata=json.loads(sig.metadata_json) if sig.metadata_json else None,
                    )
                    sig.risk_score = risk.composite_score
                    sig.risk_tier = risk.tier

                    # Add to FAISS index
                    self.pipeline.add_to_index(sig.id, processed.embedding)

                except Exception as e:
                    print(f"[Scheduler] Error processing signal {sig.id}: {e}")

            await session.commit()

            # Broadcast via WebSocket
            for sig in signals:
                signal_data = {
                    "id": sig.id,
                    "source": sig.source,
                    "title": sig.title,
                    "content": sig.content[:200],
                    "risk_score": sig.risk_score,
                    "risk_tier": sig.risk_tier,
                    "sentiment_label": sig.sentiment_label,
                    "timestamp": sig.timestamp.isoformat() if sig.timestamp else None,
                }
                await ws_manager.broadcast_signal(signal_data)

                # Alert broadcast for high/critical
                if sig.risk_tier in ("high", "critical"):
                    await ws_manager.broadcast_alert(signal_data)

            print(f"[Scheduler] Tick complete: {len(signals)} signals processed")


# Global scheduler instance
scheduler = BackgroundScheduler()
