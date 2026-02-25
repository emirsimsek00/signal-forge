"""Ingestion manager — orchestrates signal sources and persists to DB."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.ingestion.base import RawSignal, SignalSource
from backend.ingestion.demo_data import DemoDataGenerator
from backend.ingestion.reddit import RedditSource
from backend.ingestion.news import NewsSource
from backend.ingestion.zendesk import ZendeskSource
from backend.ingestion.alpha_vantage import AlphaVantageSource
from backend.ingestion.stripe import StripeSource
from backend.ingestion.pagerduty import PagerDutySource
from backend.models.signal import Signal


class IngestionManager:
    """Orchestrates signal fetching, normalization, and persistence.

    Automatically selects live sources when API keys are present,
    falls back to DemoDataGenerator otherwise.
    """

    def __init__(self) -> None:
        self.sources: list[SignalSource] = self._build_sources()

    @staticmethod
    def _build_sources() -> list[SignalSource]:
        """Register sources based on available API keys."""
        sources: list[SignalSource] = []

        # Reddit — available if client ID is set
        if settings.reddit_client_id:
            sources.append(RedditSource())
            print("[IngestionManager] ✓ Reddit source enabled")
        else:
            print("[IngestionManager] ○ Reddit source skipped (no REDDIT_CLIENT_ID)")

        # NewsAPI — available if key is set
        if settings.newsapi_key:
            sources.append(NewsSource())
            print("[IngestionManager] ✓ NewsAPI source enabled")
        else:
            print("[IngestionManager] ○ NewsAPI source skipped (no NEWSAPI_KEY)")

        # Zendesk — available if subdomain + key are set
        if settings.zendesk_subdomain and settings.zendesk_api_key:
            sources.append(ZendeskSource())
            print("[IngestionManager] ✓ Zendesk source enabled")
        else:
            print("[IngestionManager] ○ Zendesk source skipped (no ZENDESK_SUBDOMAIN/API_KEY)")

        # Stripe — available if key is set
        if settings.stripe_api_key:
            sources.append(StripeSource())
            print("[IngestionManager] ✓ Stripe source enabled")
        else:
            print("[IngestionManager] ○ Stripe source skipped (no STRIPE_API_KEY)")

        # PagerDuty — available if key is set
        if settings.pagerduty_api_key:
            sources.append(PagerDutySource())
            print("[IngestionManager] ✓ PagerDuty source enabled")
        else:
            print("[IngestionManager] ○ PagerDuty source skipped (no PAGERDUTY_API_KEY)")

        # Alpha Vantage — available if key is set
        if settings.alpha_vantage_key:
            sources.append(AlphaVantageSource())
            print("[IngestionManager] ✓ Alpha Vantage source enabled")
        else:
            print("[IngestionManager] ○ Alpha Vantage source skipped (no ALPHA_VANTAGE_KEY)")

        # Include demo data fallback only when explicitly enabled.
        if settings.enable_demo_data:
            sources.append(DemoDataGenerator())
            print("[IngestionManager] ✓ Demo data source enabled")
        else:
            print("[IngestionManager] ○ Demo data source disabled (ENABLE_DEMO_DATA=false)")

        return sources

    async def ingest_all(
        self,
        session: AsyncSession,
        limit: int = 50,
        tenant_id: str = "default",
    ) -> list[Signal]:
        """Fetch signals from all sources, normalize, and persist."""
        all_raw: list[RawSignal] = []
        per_source = max(1, limit // max(len(self.sources), 1))

        for source in self.sources:
            try:
                raw_signals = await source.fetch_signals(limit=per_source)
                all_raw.extend(raw_signals)
                print(f"[IngestionManager] Fetched {len(raw_signals)} from {source.source_name}")
            except Exception as e:
                print(f"[IngestionManager] Error fetching from {source.source_name}: {e}")

        db_signals = []
        for raw in all_raw:
            sig = Signal(
                tenant_id=tenant_id,
                source=raw.source,
                source_id=raw.source_id,
                title=raw.title,
                content=raw.content,
                timestamp=raw.timestamp,
                metadata_json=json.dumps(raw.metadata) if raw.metadata else None,
            )
            session.add(sig)
            db_signals.append(sig)

        await session.commit()

        # Refresh to get IDs
        for sig in db_signals:
            await session.refresh(sig)

        return db_signals

    async def health(self) -> dict[str, bool]:
        """Check connectivity for all sources."""
        results = {}
        for source in self.sources:
            try:
                results[source.source_name] = await source.health_check()
            except Exception:
                results[source.source_name] = False
        return results
