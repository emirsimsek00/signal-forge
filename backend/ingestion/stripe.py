"""Stripe signal source — ingests recent payment/operational events."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class StripeSource(SignalSource):
    """Fetches Stripe events and normalizes them into operational signals."""

    BASE_URL = "https://api.stripe.com/v1"

    @property
    def source_name(self) -> str:
        return "stripe"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.stripe_api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        if not settings.stripe_api_key:
            return []

        wanted_types = {
            event_type.strip()
            for event_type in settings.stripe_event_types.split(",")
            if event_type.strip()
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.BASE_URL}/events",
                params={"limit": min(max(limit * 2, 10), 100)},
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()

        events = payload.get("data", []) or []
        signals: list[RawSignal] = []
        for event in events:
            event_type = str(event.get("type") or "")
            if wanted_types and event_type not in wanted_types:
                continue

            timestamp = self._to_ts(event.get("created"))
            event_data = event.get("data", {}).get("object", {}) if isinstance(event.get("data"), dict) else {}

            amount = event_data.get("amount") or event_data.get("amount_due") or 0
            currency = (event_data.get("currency") or "").upper()
            status = event_data.get("status") or ""
            if isinstance(amount, int):
                amount_display = amount / 100.0 if currency else float(amount)
            else:
                amount_display = 0.0

            title = f"Stripe event: {event_type}"
            content_parts = [f"Received Stripe event `{event_type}`"]
            if amount_display:
                content_parts.append(f"amount={amount_display:.2f} {currency or ''}".strip())
            if status:
                content_parts.append(f"status={status}")
            content = ". ".join(content_parts) + "."

            signals.append(
                RawSignal(
                    source="stripe",
                    source_id=str(event.get("id") or ""),
                    title=title,
                    content=content,
                    timestamp=timestamp,
                    metadata={
                        "event_type": event_type,
                        "livemode": bool(event.get("livemode")),
                        "api_version": event.get("api_version"),
                        "object": event_data.get("object"),
                        "object_id": event_data.get("id"),
                        "status": status,
                        "amount": amount_display,
                        "currency": currency,
                        "urgency": self._urgency_for_event(event_type),
                        "is_anomaly": self._is_anomalous_type(event_type),
                    },
                )
            )

            if len(signals) >= limit:
                break

        return signals

    async def health_check(self) -> bool:
        if not settings.stripe_api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/events",
                    params={"limit": 1},
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _to_ts(value: int | str | None) -> datetime:
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def _is_anomalous_type(event_type: str) -> bool:
        lower = event_type.lower()
        return any(
            key in lower
            for key in ("failed", "dispute", "fraud", "chargeback", "refund")
        )

    @staticmethod
    def _urgency_for_event(event_type: str) -> str:
        lower = event_type.lower()
        if any(key in lower for key in ("dispute", "fraud", "payout.failed")):
            return "high"
        if "failed" in lower:
            return "medium"
        return "low"
