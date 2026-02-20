"""Tests for NLP pipeline and risk scorer."""

import pytest

from backend.nlp.pipeline import NLPPipeline
from backend.risk.scorer import RiskScorer


class TestNLPPipeline:
    """Test the mock NLP pipeline."""

    def test_pipeline_initializes(self):
        pipeline = NLPPipeline(use_mock=True)
        assert pipeline is not None

    def test_process_returns_result(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("Server is down. Urgent fix needed.")
        assert result is not None
        assert result.sentiment is not None
        assert result.summary is not None
        assert result.embedding is not None

    def test_sentiment_label(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("Everything is working perfectly fine.")
        assert result.sentiment.label in ("positive", "negative", "neutral", "mixed")

    def test_sentiment_score_range(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("something happened")
        assert -1.0 <= result.sentiment.raw_score <= 1.0

    def test_embedding_dimensions(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("test content for embedding")
        assert len(result.embedding) > 0
        assert all(isinstance(v, float) for v in result.embedding)

    def test_summary_not_empty(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("A significant security breach was detected in production systems.")
        assert len(result.summary) > 0

    def test_entities_extraction(self):
        pipeline = NLPPipeline(use_mock=True)
        result = pipeline.process("AWS outage affects US-East-1 region customers.")
        # Entities might be empty in mock mode, but should be a list
        assert isinstance(result.entities, list)

    def test_faiss_add_and_search(self):
        pipeline = NLPPipeline(use_mock=True)
        r1 = pipeline.process("server outage detected")
        r2 = pipeline.process("database connection timeout")
        r3 = pipeline.process("happy customer feedback")
        pipeline.add_to_index(1, r1.embedding)
        pipeline.add_to_index(2, r2.embedding)
        pipeline.add_to_index(3, r3.embedding)

        # Search for similar to the first embedding
        results = pipeline.search_similar(r1.embedding, k=2)
        assert len(results) <= 2
        # Should include the same signal or something similar
        ids = [r[0] for r in results]
        assert 1 in ids


class TestRiskScorer:
    """Test the risk scoring module."""

    def test_scorer_initializes(self):
        scorer = RiskScorer()
        assert scorer is not None

    def test_score_returns_result(self):
        scorer = RiskScorer()
        result = scorer.score(sentiment_score=-0.8)
        assert result is not None
        assert 0.0 <= result.composite_score <= 1.0
        assert result.tier in ("critical", "high", "moderate", "low")

    def test_high_negative_sentiment_generates_higher_risk(self):
        scorer = RiskScorer()
        neg_result = scorer.score(sentiment_score=-0.9)
        pos_result = scorer.score(sentiment_score=0.9)
        assert neg_result.composite_score >= pos_result.composite_score

    def test_tier_boundaries(self):
        scorer = RiskScorer()
        # Very negative should be high/critical tier
        result = scorer.score(sentiment_score=-1.0)
        assert result.tier in ("critical", "high", "moderate")

    def test_stripe_failed_event_increases_risk(self):
        scorer = RiskScorer()
        base = scorer.score(sentiment_score=0.0, source="stripe", metadata={"event_type": "payment_intent.succeeded"})
        failed = scorer.score(
            sentiment_score=0.0,
            source="stripe",
            metadata={"event_type": "charge.failed", "amount": 25000, "urgency": "high"},
        )
        assert failed.composite_score > base.composite_score
        assert failed.revenue_component >= base.revenue_component

    def test_pagerduty_triggered_high_urgency_increases_risk(self):
        scorer = RiskScorer()
        normal = scorer.score(
            sentiment_score=0.0,
            source="pagerduty",
            metadata={"status": "resolved", "urgency": "low"},
        )
        incident = scorer.score(
            sentiment_score=0.0,
            source="pagerduty",
            metadata={"status": "triggered", "urgency": "high"},
        )
        assert incident.composite_score > normal.composite_score
        assert incident.anomaly_component >= normal.anomaly_component
