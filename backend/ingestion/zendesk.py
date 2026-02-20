"""Zendesk signal source — fetches recent support tickets."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource


class ZendeskSource(SignalSource):
    """Fetch recent tickets from Zendesk."""

    @property
    def source_name(self) -> str:
        return "zendesk"

    @property
    def _base_url(self) -> str:
        return f"https://{settings.zendesk_subdomain}.zendesk.com/api/v2"

    def _auth_headers(self) -> dict[str, str]:
        # Zendesk supports email/token basic auth and OAuth bearer tokens.
        if settings.zendesk_email and settings.zendesk_api_key:
            token = base64.b64encode(
                f"{settings.zendesk_email}/token:{settings.zendesk_api_key}".encode("utf-8")
            ).decode("ascii")
            return {
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {settings.zendesk_api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_signals(self, limit: int = 50) -> list[RawSignal]:
        if not settings.zendesk_subdomain or not settings.zendesk_api_key:
            return []

        statuses = {
            status.strip().lower()
            for status in settings.zendesk_ticket_statuses.split(",")
            if status.strip()
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self._base_url}/tickets.json",
                params={"sort_by": "updated_at", "sort_order": "desc", "per_page": min(limit * 2, 100)},
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            payload = resp.json()

        tickets = payload.get("tickets", [])
        signals: list[RawSignal] = []
        for ticket in tickets:
            status = (ticket.get("status") or "").lower()
            if statuses and status not in statuses:
                continue

            subject = (ticket.get("subject") or "").strip() or "Support ticket"
            description = (ticket.get("description") or "").strip()
            content = description or subject

            updated_at = ticket.get("updated_at") or ticket.get("created_at")
            timestamp = self._parse_timestamp(updated_at)

            signals.append(
                RawSignal(
                    source="zendesk",
                    title=subject[:500],
                    content=content,
                    timestamp=timestamp,
                    source_id=str(ticket.get("id") or ""),
                    metadata={
                        "ticket_id": ticket.get("id"),
                        "status": ticket.get("status"),
                        "priority": ticket.get("priority"),
                        "type": ticket.get("type"),
                        "tags": ticket.get("tags") or [],
                        "requester_id": ticket.get("requester_id"),
                        "assignee_id": ticket.get("assignee_id"),
                        "urgency": self._priority_to_urgency(ticket.get("priority")),
                        "url": ticket.get("url"),
                    },
                )
            )
            if len(signals) >= limit:
                break

        return signals

    async def health_check(self) -> bool:
        if not settings.zendesk_subdomain or not settings.zendesk_api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"{self._base_url}/tickets.json",
                    params={"per_page": 1},
                    headers=self._auth_headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime:
        if not value:
            return datetime.now(tz=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)

    @staticmethod
    def _priority_to_urgency(priority: str | None) -> str:
        if not priority:
            return "medium"
        priority = priority.lower()
        if priority in {"urgent", "high"}:
            return "high"
        if priority in {"normal", "medium"}:
            return "medium"
        return "low"
