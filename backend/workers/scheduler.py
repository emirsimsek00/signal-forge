"""Background scheduler — auto-ingests and processes signals on an interval."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta

from backend.utils.time import utc_now
from typing import Optional

from sqlalchemy import delete, desc, func, select

from backend.config import settings
from backend.database import async_session
from backend.ingestion.manager import IngestionManager
from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer
from backend.models.risk import RiskAssessment
from backend.models.signal import Signal
from backend.models.incident import Incident
from backend.api.websocket import manager as ws_manager
from backend.anomaly.detector import detector as anomaly_detector
from backend.incident_manager import auto_incident_manager
from backend.services.notifier import notify_tenant

logger = logging.getLogger("signalforge.scheduler")


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
        self._last_daily_digest_sent: dict[str, datetime] = {}

    async def start(self) -> None:
        """Start the background scheduler."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler started (interval={self.interval}s)")

    async def stop(self) -> None:
        """Stop the background scheduler gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

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
                logger.error(f"Error in tick: {e}")
                await asyncio.sleep(10)  # back off on error

    async def _tick(self) -> None:
        """Single scheduler tick: ingest → process → score → broadcast."""
        async with async_session() as session:
            # Ingest
            signals = await self.ingestion_manager.ingest_all(
                session=session,
                limit=15,
                tenant_id="default",
            )
            if signals:
                logger.info(f"Processing {len(signals)} new signals")
                critical_contexts: list[dict] = []

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
                        sig.tenant_id = sig.tenant_id or "default"

                        session.add(
                            RiskAssessment(
                                signal_id=sig.id,
                                tenant_id=sig.tenant_id,
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

                        if sig.risk_tier == "critical":
                            critical_contexts.append(
                                {
                                    "id": sig.id,
                                    "title": sig.title or f"{sig.source} signal",
                                    "source": sig.source,
                                    "content": sig.content,
                                    "summary": sig.summary,
                                    "risk_score": sig.risk_score,
                                    "risk_tier": sig.risk_tier,
                                    "timestamp": sig.timestamp.isoformat() if sig.timestamp else None,
                                }
                            )

                        # Add to FAISS index
                        self.pipeline.add_to_index(sig.id, processed.embedding)

                    except Exception as e:
                        logger.error(f"Error processing signal {sig.id}: {e}")

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

                # Notify configured channels for critical signals.
                for context in critical_contexts:
                    try:
                        await notify_tenant("default", "critical_signal", context, session=session)
                    except Exception as e:
                        logger.error(
                            f"Critical signal notification error for signal {context.get('id')}: {e}"
                        )

                logger.info(f"Tick complete: {len(signals)} signals processed")

                # Persist FAISS index to disk
                self.pipeline.save_index()
            else:
                logger.debug("Tick: no new signals")

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
                    logger.info(f"Detected {len(anomalies)} anomalies")
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
                logger.error(f"Anomaly detection error: {e}")

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
                        logger.info(f"Generated {len(forecast_incidents)} forecast incidents")
                        created_incidents.extend(forecast_incidents)
                    self._last_forecast_incident_check = utc_now()
            except Exception as e:
                logger.error(f"Forecast incident generation error: {e}")

            try:
                resolved_incidents = await auto_incident_manager.reconcile_open_incidents(
                    session=session,
                    active_anomaly_titles=active_anomaly_titles if anomaly_detection_ok else None,
                    active_forecast_titles=active_forecast_titles,
                )
                if resolved_incidents:
                    logger.info(f"Auto-resolved {len(resolved_incidents)} incidents")
            except Exception as e:
                logger.error(f"Incident reconciliation error: {e}")

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

            # Dispatch daily digests for tenants subscribed to the trigger.
            try:
                await self._dispatch_daily_digests(session=session)
            except Exception as e:
                logger.error(f"Daily digest dispatch error: {e}")

    def _should_run_forecast_incident_check(self) -> bool:
        if self._last_forecast_incident_check is None:
            return True
        return utc_now() - self._last_forecast_incident_check >= timedelta(minutes=15)

    async def _cleanup_old_signals(self, session) -> None:
        """Delete signals older than retention_days to prevent unbounded DB growth."""
        cutoff = utc_now() - timedelta(days=settings.retention_days)
        result = await session.execute(
            delete(Signal).where(Signal.timestamp < cutoff)
        )
        if result.rowcount > 0:
            await session.commit()
            logger.info(f"Data retention: deleted {result.rowcount} signals older than {settings.retention_days} days")

    async def _dispatch_daily_digests(self, session) -> None:
        """Send daily digest notifications once per UTC day to subscribed tenants."""
        from backend.models.notification import NotificationPreference

        now = utc_now()
        tenant_result = await session.execute(
            select(NotificationPreference.tenant_id)
            .where(
                NotificationPreference.is_active,
                NotificationPreference.triggers.like("%daily_digest%"),
            )
            .distinct()
        )
        tenant_ids = [row[0] for row in tenant_result.all() if row[0]]

        for tenant_id in tenant_ids:
            if not self._should_send_daily_digest(tenant_id=tenant_id, now=now):
                continue

            digest = await self._build_daily_digest_context(
                session=session,
                tenant_id=tenant_id,
                now=now,
            )
            await notify_tenant(tenant_id, "daily_digest", digest, session=session)
            self._last_daily_digest_sent[tenant_id] = now
            logger.info(
                "Sent daily digest for tenant %s (%s signals, %s active incidents)",
                tenant_id,
                digest["total_signals"],
                digest["active_incidents"],
            )

    def _should_send_daily_digest(self, tenant_id: str, now: datetime) -> bool:
        last_sent = self._last_daily_digest_sent.get(tenant_id)
        if last_sent is None:
            return True
        return last_sent.date() != now.date()

    async def _build_daily_digest_context(self, session, tenant_id: str, now: datetime) -> dict:
        window_start = now - timedelta(hours=24)

        total_signals = (
            await session.execute(
                select(func.count(Signal.id)).where(
                    Signal.tenant_id == tenant_id,
                    Signal.timestamp >= window_start,
                )
            )
        ).scalar() or 0

        critical_signals = (
            await session.execute(
                select(func.count(Signal.id)).where(
                    Signal.tenant_id == tenant_id,
                    Signal.timestamp >= window_start,
                    Signal.risk_tier == "critical",
                )
            )
        ).scalar() or 0

        avg_risk_score = (
            await session.execute(
                select(func.avg(Signal.risk_score)).where(
                    Signal.tenant_id == tenant_id,
                    Signal.timestamp >= window_start,
                    Signal.risk_score.isnot(None),
                )
            )
        ).scalar() or 0.0

        active_incidents = (
            await session.execute(
                select(func.count(Incident.id)).where(
                    Incident.tenant_id == tenant_id,
                    Incident.status.in_(["active", "investigating"]),
                )
            )
        ).scalar() or 0

        new_incidents = (
            await session.execute(
                select(func.count(Incident.id)).where(
                    Incident.tenant_id == tenant_id,
                    Incident.start_time >= window_start,
                )
            )
        ).scalar() or 0

        top_signals_result = await session.execute(
            select(Signal)
            .where(
                Signal.tenant_id == tenant_id,
                Signal.timestamp >= window_start,
            )
            .order_by(desc(Signal.risk_score), desc(Signal.timestamp))
            .limit(5)
        )
        top_signals = [
            {
                "id": sig.id,
                "source": sig.source,
                "title": sig.title,
                "content": sig.content[:200],
                "risk_score": sig.risk_score,
                "risk_tier": sig.risk_tier,
            }
            for sig in top_signals_result.scalars().all()
        ]

        return {
            "date": now.strftime("%Y-%m-%d"),
            "total_signals": int(total_signals),
            "critical_signals": int(critical_signals),
            "active_incidents": int(active_incidents),
            "new_incidents": int(new_incidents),
            "avg_risk_score": float(avg_risk_score),
            "top_signals": top_signals,
        }


# Global scheduler instance
scheduler = BackgroundScheduler()
