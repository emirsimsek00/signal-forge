"""Text embedding generation for vector similarity and clustering."""

from __future__ import annotations

import random
import numpy as np
from dataclasses import dataclass


EMBEDDING_DIM = 384  # MiniLM-L6-v2 dimension


class EmbeddingGenerator:
    """Generates text embeddings using sentence-transformers or mock."""

    def __init__(self, use_mock: bool = True) -> None:
        self.use_mock = use_mock
        self._model = None

    def _load_model(self):
        if self._model is None and not self.use_mock:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, text: str) -> list[float]:
        if self.use_mock:
            return self._mock_embed(text)

        self._load_model()
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.use_mock:
            return [self._mock_embed(t) for t in texts]

        self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    def _mock_embed(self, text: str) -> list[float]:
        """Deterministic-ish mock embedding based on text hash."""
        seed = hash(text) % (2**31)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
        # Normalize
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec]
