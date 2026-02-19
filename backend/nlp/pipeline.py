"""NLP Pipeline — orchestrates all NLP tasks for signal processing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from backend.nlp.sentiment import SentimentAnalyzer, SentimentResult
from backend.nlp.entities import EntityExtractor, Entity
from backend.nlp.embeddings import EmbeddingGenerator
from backend.nlp.summarizer import Summarizer


@dataclass
class ProcessedSignal:
    """Result of running the full NLP pipeline on a signal."""

    sentiment: SentimentResult
    entities: list[Entity]
    summary: str
    embedding: list[float]


class NLPPipeline:
    """Orchestrates all NLP processing tasks."""

    def __init__(self, use_mock: bool = True) -> None:
        self.sentiment_analyzer = SentimentAnalyzer(use_mock=use_mock)
        self.entity_extractor = EntityExtractor(use_mock=use_mock)
        self.embedding_generator = EmbeddingGenerator(use_mock=use_mock)
        self.summarizer = Summarizer(use_mock=use_mock)

    def process(self, text: str) -> ProcessedSignal:
        """Run full NLP pipeline on text."""
        sentiment = self.sentiment_analyzer.analyze(text)
        entities = self.entity_extractor.extract(text)
        summary = self.summarizer.summarize(text)
        embedding = self.embedding_generator.embed(text)

        return ProcessedSignal(
            sentiment=sentiment,
            entities=entities,
            summary=summary,
            embedding=embedding,
        )

    def process_batch(self, texts: list[str]) -> list[ProcessedSignal]:
        """Process multiple texts."""
        embeddings = self.embedding_generator.embed_batch(texts)
        results = []
        for i, text in enumerate(texts):
            sentiment = self.sentiment_analyzer.analyze(text)
            entities = self.entity_extractor.extract(text)
            summary = self.summarizer.summarize(text)
            results.append(ProcessedSignal(
                sentiment=sentiment,
                entities=entities,
                summary=summary,
                embedding=embeddings[i],
            ))
        return results

    # ── FAISS Index Operations ───────────────────────────────────

    def add_to_index(self, signal_id: int, embedding: list[float]) -> None:
        """Add a signal's embedding to the FAISS index."""
        self.embedding_generator.add_to_index(signal_id, embedding)

    def add_batch_to_index(self, signal_ids: list[int], embeddings: list[list[float]]) -> None:
        """Add multiple signal embeddings to the FAISS index."""
        self.embedding_generator.add_batch_to_index(signal_ids, embeddings)

    def find_similar(self, embedding: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Find k most similar signals by embedding cosine similarity."""
        return self.embedding_generator.find_similar(embedding, k)

    def save_index(self) -> None:
        self.embedding_generator.save_index()

    def load_index(self) -> None:
        self.embedding_generator.load_index()

    @property
    def index_size(self) -> int:
        return self.embedding_generator.index_size
