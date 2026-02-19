"""Sentiment analysis — wraps HuggingFace or provides mock implementation."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class SentimentResult:
    label: str  # "positive", "negative", "neutral"
    score: float  # 0.0 to 1.0 confidence
    raw_score: float  # -1.0 to 1.0 (negative to positive)


class SentimentAnalyzer:
    """Analyzes text sentiment using HuggingFace or mock inference."""

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock
        self._pipeline = None

    def _load_model(self):
        if self._pipeline is None and not self.use_mock:
            from transformers import pipeline
            self._pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                return_all_scores=False,
            )

    def analyze(self, text: str) -> SentimentResult:
        if self.use_mock:
            return self._mock_analyze(text)

        self._load_model()
        result = self._pipeline(text[:512])[0]
        label = result["label"].lower()
        score = result["score"]

        if label == "positive":
            raw_score = score
        else:
            raw_score = -score
            label = "negative"

        return SentimentResult(label=label, score=score, raw_score=raw_score)

    def _mock_analyze(self, text: str) -> SentimentResult:
        """Keyword-based mock sentiment for demo mode."""
        text_lower = text.lower()
        negative_words = [
            "error", "fail", "outage", "broken", "slow", "issue", "bug",
            "crash", "down", "problem", "complaint", "unacceptable", "breach",
            "decline", "drop", "concern", "timeout", "degraded", "spike",
            "overcharged", "loop", "discrepancy",
        ]
        positive_words = [
            "great", "excellent", "love", "fast", "resolved", "improved",
            "success", "growth", "loving", "shoutout", "walkthrough",
            "new feature", "unique", "surge",
        ]

        neg_count = sum(1 for w in negative_words if w in text_lower)
        pos_count = sum(1 for w in positive_words if w in text_lower)

        if neg_count > pos_count:
            raw_score = -min(0.95, 0.5 + neg_count * 0.1 + random.uniform(0, 0.15))
            return SentimentResult(label="negative", score=abs(raw_score), raw_score=raw_score)
        elif pos_count > neg_count:
            raw_score = min(0.95, 0.5 + pos_count * 0.1 + random.uniform(0, 0.15))
            return SentimentResult(label="positive", score=raw_score, raw_score=raw_score)
        else:
            raw_score = random.uniform(-0.2, 0.2)
            return SentimentResult(
                label="neutral",
                score=0.5 + abs(raw_score),
                raw_score=raw_score,
            )
