"""NLP Pipeline — orchestrates all NLP tasks for signal processing."""

from __future__ import annotations

import json
from dataclasses import dataclass

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
