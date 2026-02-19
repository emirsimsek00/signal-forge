"""Ingestion manager — orchestrates signal sources and persists to DB."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.ingestion.base import RawSignal
from backend.ingestion.demo_data import DemoDataGenerator
from backend.models.signal import Signal


class IngestionManager:
    """Orchestrates signal fetching, normalization, and persistence."""

    def __init__(self) -> None:
        self.sources = [DemoDataGenerator()]

    async def ingest_all(self, session: AsyncSession, limit: int = 50) -> list[Signal]:
        """Fetch signals from all sources, normalize, and persist."""
        all_raw: list[RawSignal] = []
        for source in self.sources:
            try:
                raw_signals = await source.fetch_signals(limit=limit)
                all_raw.extend(raw_signals)
            except Exception as e:
                print(f"[IngestionManager] Error fetching from {source.source_name}: {e}")

        db_signals = []
        for raw in all_raw:
            sig = Signal(
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
