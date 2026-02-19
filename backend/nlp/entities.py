"""Named Entity Recognition — extracts entities from text."""

from __future__ import annotations

import re
import random
from dataclasses import dataclass


@dataclass
class Entity:
    text: str
    label: str  # PER, ORG, LOC, MISC, METRIC, PRODUCT
    start: int
    end: int


class EntityExtractor:
    """Extracts named entities using HuggingFace NER or mock."""

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock
        self._pipeline = None

    def _load_model(self):
        if self._pipeline is None and not self.use_mock:
            from transformers import pipeline
            self._pipeline = pipeline(
                "ner",
                model="dslim/bert-base-NER",
                aggregation_strategy="simple",
            )

    def extract(self, text: str) -> list[Entity]:
        if self.use_mock:
            return self._mock_extract(text)

        self._load_model()
        results = self._pipeline(text[:512])
        return [
            Entity(
                text=r["word"],
                label=r["entity_group"],
                start=r["start"],
                end=r["end"],
            )
            for r in results
        ]

    def _mock_extract(self, text: str) -> list[Entity]:
        """Pattern-based mock entity extraction."""
        entities: list[Entity] = []

        # Organizations
        org_patterns = [
            "SignalForge", "Reddit", "Zendesk", "Stripe", "PagerDuty",
            "AWS", "GCP", "TechCrunch", "Reuters", "Bloomberg",
        ]
        for org in org_patterns:
            for m in re.finditer(re.escape(org), text, re.IGNORECASE):
                entities.append(Entity(text=org, label="ORG", start=m.start(), end=m.end()))

        # Metrics / numbers
        for m in re.finditer(r'\b\d+(?:\.\d+)?%?\b', text):
            entities.append(Entity(text=m.group(), label="METRIC", start=m.start(), end=m.end()))

        # People names in metadata context
        name_patterns = ["Alice", "Bob", "Carlos", "Dana"]
        for name in name_patterns:
            for m in re.finditer(re.escape(name), text):
                entities.append(Entity(text=name, label="PER", start=m.start(), end=m.end()))

        return entities
