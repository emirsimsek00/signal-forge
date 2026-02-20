"""PagerDuty signal source — ingests recent incident activity."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class PagerDutySource(SignalSource):
    """Fetches incident signals from PagerDuty REST API."""

    BASE_URL = "https://api.pagerduty.com"

    @property
    def source_name(self) -> str:
        return "pagerduty"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token token={settings.pagerduty_api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        if not settings.pagerduty_api_key:
            return []

        params: dict[str, str | int] = {
            "limit": min(max(limit * 2, 10), 100),
            "sort_by": "created_at:desc",
        }
        service_ids = [
            value.strip()
            for value in settings.pagerduty_service_ids.split(",")
            if value.strip()
        ]
        # PagerDuty expects repeated `service_ids[]` params.
        query_items: list[tuple[str, str | int]] = list(params.items())
        query_items.extend(("service_ids[]", service_id) for service_id in service_ids)

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.BASE_URL}/incidents",
                params=query_items,
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()

        incidents = payload.get("incidents", []) or []
        signals: list[RawSignal] = []
        for incident in incidents:
            urgency = (incident.get("urgency") or "").lower()
            status = (incident.get("status") or "").lower()
            title = incident.get("title") or "PagerDuty incident"
            service = incident.get("service") or {}
            service_name = service.get("summary") or "unknown-service"

            created_at = incident.get("created_at") or incident.get("last_status_change_at")
            timestamp = self._to_ts(created_at)

            content = (
                f"PagerDuty incident `{title}` on {service_name} "
                f"(status={status or 'unknown'}, urgency={urgency or 'unknown'})."
            )

            signals.append(
                RawSignal(
                    source="pagerduty",
                    source_id=str(incident.get("id") or ""),
                    title=title,
                    content=content,
                    timestamp=timestamp,
                    metadata={
                        "incident_number": incident.get("incident_number"),
                        "status": status,
                        "urgency": urgency or "medium",
                        "service_id": service.get("id"),
                        "service_name": service_name,
                        "html_url": incident.get("html_url"),
                        "is_anomaly": urgency == "high" or status == "triggered",
                    },
                )
            )

            if len(signals) >= limit:
                break

        return signals

    async def health_check(self) -> bool:
        if not settings.pagerduty_api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/incidents",
                    params={"limit": 1},
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _to_ts(value: str | None) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)
