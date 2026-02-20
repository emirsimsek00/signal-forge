"""Automatic incident lifecycle management from anomaly and forecast intelligence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.anomaly.detector import AnomalyEvent
from backend.forecasting.engine import ForecastEngine, ForecastResult
from backend.models.incident import Incident
from backend.models.signal import Signal


class AutoIncidentManager:
    """Creates, de-duplicates, escalates, and resolves intelligence-driven incidents."""

    _SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self, forecast_engine: ForecastEngine | None = None) -> None:
        self.forecast_engine = forecast_engine or ForecastEngine()

    def anomaly_titles(self, anomalies: list[AnomalyEvent]) -> set[str]:
        return {self._anomaly_title(anomaly) for anomaly in anomalies}

    async def collect_forecast_concerns(
        self,
        session: AsyncSession,
        max_metrics: int = 6,
        lookback_hours: int = 168,
        horizon: int = 8,
    ) -> list[dict[str, Any]]:
        metrics = await self.forecast_engine.list_metric_names(
            session=session,
            lookback_hours=lookback_hours,
        )

        concerns: list[dict[str, Any]] = []
        for metric_name in metrics[:max_metrics]:
            forecast = await self.forecast_engine.generate(
                session=session,
                metric_name=metric_name,
                horizon=horizon,
                lookback_hours=lookback_hours,
            )
            insight = self._evaluate_forecast(metric_name, forecast)
            if not insight:
                continue

            concerns.append(
                {
                    "metric_name": metric_name,
                    "forecast": forecast,
                    "insight": insight,
                    "title": self._forecast_title(metric_name, insight["direction"]),
                }
            )
        return concerns

    async def create_from_anomalies(
        self,
        session: AsyncSession,
        anomalies: list[AnomalyEvent],
    ) -> list[Incident]:
        created: list[Incident] = []
        for anomaly in anomalies:
            title = self._anomaly_title(anomaly)
            related_ids = anomaly.affected_signal_ids or []
            existing = await self._get_open_incident_by_title(session=session, title=title)
            if existing:
                self._refresh_existing_incident(
                    incident=existing,
                    severity=self._map_anomaly_severity(anomaly.severity),
                    description=(
                        f"{anomaly.description}. "
                        f"Observed value {anomaly.metric_value:.3f} exceeded threshold {anomaly.threshold:.3f}."
                    ),
                    root_cause=self._anomaly_hypothesis(anomaly),
                    actions=self._anomaly_actions(anomaly),
                    related_signal_ids=related_ids,
                )
                continue

            incident = Incident(
                title=title,
                description=(
                    f"{anomaly.description}. "
                    f"Observed value {anomaly.metric_value:.3f} exceeded threshold {anomaly.threshold:.3f}."
                ),
                severity=self._map_anomaly_severity(anomaly.severity),
                status="investigating",
                start_time=anomaly.detected_at,
                related_signal_ids_json=json.dumps(related_ids),
                root_cause_hypothesis=self._anomaly_hypothesis(anomaly),
                recommended_actions=self._anomaly_actions(anomaly),
            )
            session.add(incident)
            created.append(incident)

        if created:
            await session.flush()
        return created

    async def create_from_forecasts(
        self,
        session: AsyncSession,
        max_metrics: int = 6,
        lookback_hours: int = 168,
        horizon: int = 8,
        concerns: Optional[list[dict[str, Any]]] = None,
    ) -> list[Incident]:
        if concerns is None:
            concerns = await self.collect_forecast_concerns(
                session=session,
                max_metrics=max_metrics,
                lookback_hours=lookback_hours,
                horizon=horizon,
            )

        created: list[Incident] = []
        for concern in concerns:
            metric_name = concern["metric_name"]
            forecast: ForecastResult = concern["forecast"]
            insight: dict[str, str] = concern["insight"]
            title = concern["title"]

            related_ids = await self._find_metric_signal_ids(
                session=session,
                metric_name=metric_name,
                window_hours=48,
                limit=20,
            )
            existing = await self._get_open_incident_by_title(session=session, title=title)
            if existing:
                self._refresh_existing_incident(
                    incident=existing,
                    severity=insight["severity"],
                    description=insight["description"],
                    root_cause=insight["hypothesis"],
                    actions=insight["actions"],
                    related_signal_ids=related_ids,
                )
                continue

            incident = Incident(
                title=title,
                description=insight["description"],
                severity=insight["severity"],
                status="investigating",
                start_time=forecast.generated_at,
                related_signal_ids_json=json.dumps(related_ids),
                root_cause_hypothesis=insight["hypothesis"],
                recommended_actions=insight["actions"],
            )
            session.add(incident)
            created.append(incident)

        if created:
            await session.flush()
        return created

    async def reconcile_open_incidents(
        self,
        session: AsyncSession,
        active_anomaly_titles: set[str] | None,
        active_forecast_titles: set[str] | None = None,
        anomaly_grace_minutes: int = 90,
        forecast_grace_minutes: int = 180,
    ) -> list[Incident]:
        """Resolve stale auto-generated incidents once source signals normalize."""
        result = await session.execute(
            select(Incident)
            .where(Incident.status.in_(["active", "investigating"]))
            .where((Incident.title.like("[Anomaly]%")) | (Incident.title.like("[Forecast]%")))
            .order_by(desc(Incident.start_time))
        )
        incidents = result.scalars().all()
        now = datetime.utcnow()
        resolved: list[Incident] = []

        for incident in incidents:
            started = incident.start_time or now
            if incident.title.startswith("[Anomaly]") and active_anomaly_titles is not None:
                is_stale = (
                    incident.title not in active_anomaly_titles
                    and now - started >= timedelta(minutes=anomaly_grace_minutes)
                )
            elif incident.title.startswith("[Forecast]") and active_forecast_titles is not None:
                is_stale = (
                    incident.title not in active_forecast_titles
                    and now - started >= timedelta(minutes=forecast_grace_minutes)
                )
            else:
                is_stale = False

            if not is_stale:
                continue

            incident.status = "resolved"
            incident.end_time = now
            note = f"Auto-resolved at {now.isoformat()} after normalization window."
            if incident.recommended_actions:
                incident.recommended_actions = f"{incident.recommended_actions}\n{note}"
            else:
                incident.recommended_actions = note
            resolved.append(incident)

        if resolved:
            await session.flush()
        return resolved

    async def _find_metric_signal_ids(
        self,
        session: AsyncSession,
        metric_name: str,
        window_hours: int,
        limit: int,
    ) -> list[int]:
        since = datetime.utcnow() - timedelta(hours=window_hours)
        result = await session.execute(
            select(Signal.id, Signal.metadata_json)
            .where(Signal.timestamp >= since, Signal.metadata_json.isnot(None))
            .where(Signal.source.in_(["financial", "system", "stripe", "pagerduty"]))
            .order_by(desc(Signal.timestamp))
            .limit(2500)
        )

        related: list[int] = []
        for signal_id, metadata_json in result.all():
            if not metadata_json:
                continue
            try:
                metadata = json.loads(metadata_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if metadata.get("metric_name") == metric_name:
                related.append(int(signal_id))
                if len(related) >= limit:
                    break
        return related

    async def _get_open_incident_by_title(
        self,
        session: AsyncSession,
        title: str,
    ) -> Incident | None:
        result = await session.execute(
            select(Incident)
            .where(Incident.title == title)
            .where(Incident.status.in_(["active", "investigating"]))
            .order_by(desc(Incident.start_time))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _refresh_existing_incident(
        self,
        incident: Incident,
        severity: str,
        description: str,
        root_cause: str,
        actions: str,
        related_signal_ids: list[int],
    ) -> None:
        incident.severity = self._max_severity(incident.severity, severity)
        incident.status = "investigating"
        incident.end_time = None
        incident.description = description
        incident.root_cause_hypothesis = root_cause
        incident.recommended_actions = actions
        incident.related_signal_ids_json = json.dumps(
            self._merge_related_ids(incident.related_signal_ids_json, related_signal_ids)
        )

    def _max_severity(self, existing: str, incoming: str) -> str:
        existing_rank = self._SEVERITY_RANK.get(existing, 2)
        incoming_rank = self._SEVERITY_RANK.get(incoming, 2)
        return existing if existing_rank >= incoming_rank else incoming

    @staticmethod
    def _merge_related_ids(existing_json: str | None, incoming: list[int]) -> list[int]:
        current: list[int] = []
        if existing_json:
            try:
                parsed = json.loads(existing_json)
                if isinstance(parsed, list):
                    current = [int(x) for x in parsed if isinstance(x, int)]
            except (json.JSONDecodeError, TypeError, ValueError):
                current = []
        merged = sorted(set(current + [int(x) for x in incoming]))
        return merged[:200]

    @staticmethod
    def _anomaly_title(anomaly: AnomalyEvent) -> str:
        return f"[Anomaly] {anomaly.title}"

    @staticmethod
    def _forecast_title(metric_name: str, direction: str) -> str:
        return f"[Forecast] {metric_name} {direction} trend risk"

    @staticmethod
    def _map_anomaly_severity(severity: str) -> str:
        if severity == "critical":
            return "critical"
        if severity == "high":
            return "high"
        return "medium"

    @staticmethod
    def _anomaly_hypothesis(anomaly: AnomalyEvent) -> str:
        if anomaly.type == "volume_spike":
            return "Cross-channel event volume spike suggests emerging operational incident."
        if anomaly.type == "risk_spike":
            return "Composite risk acceleration indicates correlated high-impact signals."
        return "Sentiment drift indicates growing user/customer impact perception."

    @staticmethod
    def _anomaly_actions(anomaly: AnomalyEvent) -> str:
        return "\n".join(
            [
                "1. Correlate top affected signals with recent deployments/incidents.",
                "2. Assign an incident owner and triage impacted components.",
                "3. Increase monitoring frequency until anomaly metrics normalize.",
                f"4. Review source `{anomaly.affected_source or 'cross-source'}` for root-cause evidence.",
            ]
        )

    def _evaluate_forecast(
        self,
        metric_name: str,
        forecast: ForecastResult,
    ) -> dict[str, str] | None:
        if (
            forecast.confidence < 0.6
            or not forecast.observed_points
            or not forecast.predicted_values
        ):
            return None

        observed_last = forecast.observed_points[-1].value
        predicted_last = forecast.predicted_values[-1].value
        if observed_last == 0:
            return None

        change_ratio = (predicted_last - observed_last) / abs(observed_last)
        metric = metric_name.lower()

        higher_is_bad = any(k in metric for k in ["churn", "latency", "error", "cac", "cost"])
        lower_is_bad = any(
            k in metric for k in ["mrr", "arr", "revenue", "throughput", "request_rate", "engagement"]
        )

        is_concerning = False
        direction = "increasing"
        if higher_is_bad and change_ratio >= 0.08:
            is_concerning = True
            direction = "increasing"
        elif lower_is_bad and change_ratio <= -0.08:
            is_concerning = True
            direction = "declining"
        elif not higher_is_bad and not lower_is_bad and abs(change_ratio) >= 0.15:
            is_concerning = True
            direction = "increasing" if change_ratio > 0 else "declining"

        if not is_concerning:
            return None

        severity = "critical" if abs(change_ratio) >= 0.2 and forecast.confidence >= 0.7 else "high"
        direction_word = "upward" if change_ratio > 0 else "downward"
        description = (
            f"Forecast indicates {direction_word} pressure for `{metric_name}`. "
            f"Projected change is {change_ratio:+.1%} from latest observed value "
            f"with {forecast.confidence:.0%} confidence."
        )
        hypothesis = (
            f"Trend shift in `{metric_name}` may be linked to correlated system/support/financial changes."
        )
        actions = "\n".join(
            [
                "1. Validate forecast against recent anomaly and ticket trends.",
                "2. Run correlation graph on related signals to identify leading indicators.",
                "3. Define mitigation owner and watch thresholds for next cycle.",
            ]
        )
        return {
            "severity": severity,
            "direction": direction,
            "description": description,
            "hypothesis": hypothesis,
            "actions": actions,
        }


auto_incident_manager = AutoIncidentManager()
