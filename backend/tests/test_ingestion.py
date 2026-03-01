"""Tests for ingestion sources and manager."""

from datetime import datetime, timedelta

from backend.utils.time import utc_now

import pytest

from backend.ingestion.demo_data import DemoDataGenerator
from backend.ingestion.manager import IngestionManager


class TestDemoDataGenerator:
    """Validate demo ingestion source behavior."""

    @pytest.mark.asyncio
    async def test_fetch_signals_respects_limit(self):
        source = DemoDataGenerator()
        signals = await source.fetch_signals(limit=10)
        assert len(signals) == 10

    @pytest.mark.asyncio
    async def test_fetch_signals_shape(self):
        source = DemoDataGenerator()
        signals = await source.fetch_signals(limit=5)
        for sig in signals:
            assert sig.source
            assert sig.content
            assert sig.timestamp is not None

    @pytest.mark.asyncio
    async def test_fetch_signals_recent_timestamps(self):
        source = DemoDataGenerator()
        now = utc_now().replace(tzinfo=None)
        signals = await source.fetch_signals(limit=20)
        for sig in signals:
            delta = abs((now - sig.timestamp.replace(tzinfo=None)).total_seconds())
            assert delta <= timedelta(hours=72).total_seconds() + 120


class TestIngestionManager:
    """Validate manager orchestration and persistence."""

    def test_manager_registers_demo_source(self):
        manager = IngestionManager()
        source_names = [source.source_name for source in manager.sources]
        assert "demo" in source_names

    @pytest.mark.asyncio
    async def test_ingest_all_persists_records(self, db_session):
        manager = IngestionManager()
        signals = await manager.ingest_all(db_session, limit=6)
        assert len(signals) > 0
        for sig in signals:
            assert sig.id is not None
            assert sig.source is not None
            assert sig.content
            assert sig.tenant_id == "default"

    @pytest.mark.asyncio
    async def test_ingest_all_respects_tenant_id(self, db_session):
        manager = IngestionManager()
        signals = await manager.ingest_all(db_session, limit=4, tenant_id="tenant-test")
        assert len(signals) > 0
        for sig in signals:
            assert sig.tenant_id == "tenant-test"
