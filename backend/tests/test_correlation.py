"""Tests for the correlation engine."""

import json
from datetime import datetime, timedelta

import pytest

from backend.correlation.correlator import SignalCorrelator
from backend.correlation.graph import build_graph
from backend.models.signal import Signal
from backend.nlp.pipeline import NLPPipeline


def _embed(value: float) -> list[float]:
    return [value] * 384


@pytest.fixture
def correlator() -> SignalCorrelator:
    return SignalCorrelator(pipeline=NLPPipeline(use_mock=True))


@pytest.fixture
def sample_signals():
    now = datetime.utcnow()
    return [
        Signal(
            id=1,
            source="reddit",
            source_id="r-1",
            title="Checkout outage reported",
            content="Users report outage and 500 errors on checkout API.",
            timestamp=now - timedelta(minutes=10),
            sentiment_label="negative",
            entities_json=json.dumps([{"text": "checkout", "label": "PRODUCT"}]),
            embedding_json=json.dumps(_embed(0.95)),
            risk_score=0.8,
            risk_tier="high",
        ),
        Signal(
            id=2,
            source="zendesk",
            source_id="z-1",
            title="Support ticket spike",
            content="Ticket surge related to checkout failures.",
            timestamp=now - timedelta(minutes=18),
            sentiment_label="negative",
            entities_json=json.dumps([{"text": "checkout", "label": "PRODUCT"}]),
            embedding_json=json.dumps(_embed(0.90)),
            risk_score=0.7,
            risk_tier="high",
        ),
        Signal(
            id=3,
            source="news",
            source_id="n-1",
            title="Cloud provider latency event",
            content="Latency issues observed in cloud region.",
            timestamp=now - timedelta(minutes=45),
            sentiment_label="neutral",
            entities_json=json.dumps([{"text": "cloud", "label": "ORG"}]),
            embedding_json=json.dumps(_embed(0.40)),
            risk_score=0.4,
            risk_tier="moderate",
        ),
        Signal(
            id=4,
            source="financial",
            source_id="f-1",
            title="Revenue dip",
            content="Revenue dropped 3 percent after service disruption.",
            timestamp=now - timedelta(minutes=25),
            sentiment_label="negative",
            entities_json=json.dumps([{"text": "revenue", "label": "METRIC"}]),
            embedding_json=json.dumps(_embed(0.85)),
            risk_score=0.75,
            risk_tier="high",
        ),
    ]


class TestSignalCorrelator:
    def test_initializes(self, correlator: SignalCorrelator):
        assert correlator is not None

    @pytest.mark.asyncio
    async def test_correlate_returns_results(self, correlator: SignalCorrelator, db_session, sample_signals):
        for sig in sample_signals:
            db_session.add(sig)
        await db_session.commit()

        results = await correlator.correlate(signal_id=1, session=db_session, k=3)
        assert len(results) > 0
        assert len(results) <= 3
        for corr in results:
            assert corr.related_signal_id != 1
            assert 0.0 <= corr.score <= 1.0
            assert corr.method
            assert corr.explanation

    @pytest.mark.asyncio
    async def test_build_graph_returns_nodes_and_edges(
        self,
        correlator: SignalCorrelator,
        db_session,
        sample_signals,
    ):
        for sig in sample_signals:
            db_session.add(sig)
        await db_session.commit()

        graph = await build_graph(
            center_signal_id=1,
            session=db_session,
            correlator=correlator,
            depth=1,
            k_per_node=3,
        )
        assert len(graph.nodes) >= 1
        assert any(node.id == 1 for node in graph.nodes)
        assert len(graph.edges) >= 1
