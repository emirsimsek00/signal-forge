"""Background scheduler — auto-ingests and processes signals on an interval."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

from backend.config import settings
from backend.database import async_session
from backend.ingestion.manager import IngestionManager
from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer
from backend.models.risk import RiskAssessment
from backend.api.websocket import manager as ws_manager
from backend.anomaly.detector import detector as anomaly_detector
from backend.incident_manager import auto_incident_manager


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
        self._last_forecast_incident_check: Optional[datetime] = None

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
            if signals:
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
                        metadata = None
                        if sig.metadata_json:
                            try:
                                metadata = json.loads(sig.metadata_json)
                            except json.JSONDecodeError:
                                metadata = None
                        risk = self.risk_scorer.score(
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
            else:
                print("[Scheduler] Tick: no new signals")

            # Run anomaly detection
            created_incidents = []
            resolved_incidents = []
            active_anomaly_titles: set[str] = set()
            anomaly_detection_ok = False
            active_forecast_titles: set[str] | None = None
            try:
                anomalies = await anomaly_detector.run_detection(session)
                anomaly_detection_ok = True
                active_anomaly_titles = auto_incident_manager.anomaly_titles(anomalies)
                if anomalies:
                    print(f"[Scheduler] Detected {len(anomalies)} anomalies")
                    auto_anomaly_incidents = await auto_incident_manager.create_from_anomalies(
                        session=session,
                        anomalies=anomalies,
                    )
                    created_incidents.extend(auto_anomaly_incidents)
                    for anomaly in anomalies:
                        await ws_manager.broadcast_alert({
                            "type": "anomaly",
                            "anomaly_type": anomaly.type,
                            "severity": anomaly.severity,
                            "title": anomaly.title,
                            "description": anomaly.description,
                            "detected_at": anomaly.detected_at.isoformat(),
                        })
            except Exception as e:
                print(f"[Scheduler] Anomaly detection error: {e}")

            # Generate incidents from concerning metric forecasts on a slower cadence.
            try:
                if self._should_run_forecast_incident_check():
                    forecast_concerns = await auto_incident_manager.collect_forecast_concerns(
                        session=session,
                        max_metrics=6,
                        lookback_hours=168,
                        horizon=8,
                    )
                    active_forecast_titles = {concern["title"] for concern in forecast_concerns}
                    forecast_incidents = await auto_incident_manager.create_from_forecasts(
                        session=session,
                        concerns=forecast_concerns,
                    )
                    if forecast_incidents:
                        print(f"[Scheduler] Generated {len(forecast_incidents)} forecast incidents")
                        created_incidents.extend(forecast_incidents)
                    self._last_forecast_incident_check = datetime.utcnow()
            except Exception as e:
                print(f"[Scheduler] Forecast incident generation error: {e}")

            try:
                resolved_incidents = await auto_incident_manager.reconcile_open_incidents(
                    session=session,
                    active_anomaly_titles=active_anomaly_titles if anomaly_detection_ok else None,
                    active_forecast_titles=active_forecast_titles,
                )
                if resolved_incidents:
                    print(f"[Scheduler] Auto-resolved {len(resolved_incidents)} incidents")
            except Exception as e:
                print(f"[Scheduler] Incident reconciliation error: {e}")

            if created_incidents or resolved_incidents:
                await session.commit()
                for incident in created_incidents:
                    await ws_manager.broadcast_alert(
                        {
                            "type": "incident",
                            "incident_id": incident.id,
                            "title": incident.title,
                            "severity": incident.severity,
                            "status": incident.status,
                            "timestamp": incident.start_time.isoformat()
                            if incident.start_time
                            else None,
                        }
                    )
                for incident in resolved_incidents:
                    await ws_manager.broadcast_alert(
                        {
                            "type": "incident_resolved",
                            "incident_id": incident.id,
                            "title": incident.title,
                            "severity": incident.severity,
                            "status": incident.status,
                            "timestamp": incident.end_time.isoformat()
                            if incident.end_time
                            else None,
                        }
                    )

    def _should_run_forecast_incident_check(self) -> bool:
        if self._last_forecast_incident_check is None:
            return True
        # Forecast checks are heavier; run at most every 15 minutes.
        return datetime.utcnow() - self._last_forecast_incident_check >= timedelta(minutes=15)


# Global scheduler instance
scheduler = BackgroundScheduler()
