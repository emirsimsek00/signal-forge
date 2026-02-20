"""Text embedding generation with FAISS vector index for similarity search."""

from __future__ import annotations

import os
import random
from typing import Optional

import numpy as np

EMBEDDING_DIM = 384  # MiniLM-L6-v2 dimension


class EmbeddingGenerator:
    """Generates text embeddings and manages a FAISS index for similarity search."""

    def __init__(self, use_mock: bool = True, index_path: Optional[str] = None) -> None:
        self.use_mock = use_mock
        self._model = None
        self._index = None
        self._id_map: list[int] = []  # maps FAISS position → signal ID
        self._index_path = index_path or "faiss_index.bin"
        self._idmap_path = self._index_path + ".ids"

    def _load_model(self):
        if self._model is None and not self.use_mock:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def _ensure_index(self):
        """Lazily create or load the FAISS index."""
        if self._index is not None:
            return
        try:
            import faiss
            if os.path.exists(self._index_path) and os.path.exists(self._idmap_path):
                self._index = faiss.read_index(self._index_path)
                self._id_map = list(np.load(self._idmap_path, allow_pickle=True))
                print(f"[FAISS] Loaded index with {self._index.ntotal} vectors")
            else:
                self._index = faiss.IndexFlatIP(EMBEDDING_DIM)  # Inner product (cosine on normalized vecs)
                print("[FAISS] Created new index")
        except ImportError:
            # faiss not installed — use in-memory fallback
            self._index = _InMemoryIndex(EMBEDDING_DIM)
            print("[FAISS] Using in-memory fallback (faiss-cpu not installed)")

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

    def add_to_index(self, signal_id: int, embedding: list[float]) -> None:
        """Add a signal embedding to the FAISS index."""
        self._ensure_index()
        try:
            vec = self._coerce_embedding(embedding).reshape(1, -1)
        except ValueError:
            return
        self._index.add(vec)
        self._id_map.append(signal_id)

    def add_batch_to_index(self, signal_ids: list[int], embeddings: list[list[float]]) -> None:
        """Add multiple signal embeddings to the FAISS index."""
        if not embeddings or not signal_ids:
            return
        self._ensure_index()
        vecs_list: list[np.ndarray] = []
        valid_signal_ids: list[int] = []
        for signal_id, embedding in zip(signal_ids, embeddings):
            try:
                vecs_list.append(self._coerce_embedding(embedding))
                valid_signal_ids.append(signal_id)
            except ValueError:
                continue

        if not vecs_list:
            return

        vecs = np.stack(vecs_list).astype(np.float32)
        self._index.add(vecs)
        self._id_map.extend(valid_signal_ids)

    def find_similar(self, embedding: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Find k most similar signals by embedding.

        Returns list of (signal_id, similarity_score) sorted by descending similarity.
        """
        self._ensure_index()
        if self._index.ntotal == 0:
            return []

        k = min(k, self._index.ntotal)
        try:
            vec = self._coerce_embedding(embedding).reshape(1, -1)
        except ValueError:
            return []
        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._id_map):
                results.append((self._id_map[idx], float(score)))
        return results

    def save_index(self) -> None:
        """Persist FAISS index to disk."""
        if self._index is None or isinstance(self._index, _InMemoryIndex):
            return
        try:
            import faiss
            faiss.write_index(self._index, self._index_path)
            np.save(self._idmap_path, np.array(self._id_map))
            print(f"[FAISS] Saved index ({self._index.ntotal} vectors)")
        except Exception as e:
            print(f"[FAISS] Error saving index: {e}")

    def load_index(self) -> None:
        """Load FAISS index from disk."""
        self._index = None
        self._id_map = []
        self._ensure_index()

    @property
    def index_size(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal

    def _mock_embed(self, text: str) -> list[float]:
        """Deterministic-ish mock embedding based on text hash."""
        seed = hash(text) % (2**31)
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec]

    def _coerce_embedding(self, embedding: list[float]) -> np.ndarray:
        """Normalize, reshape, and dimension-correct embeddings for stable indexing/search."""
        vec = np.asarray(embedding, dtype=np.float32).flatten()
        if vec.size == 0:
            raise ValueError("empty embedding")

        if vec.size > EMBEDDING_DIM:
            vec = vec[:EMBEDDING_DIM]
        elif vec.size < EMBEDDING_DIM:
            vec = np.pad(vec, (0, EMBEDDING_DIM - vec.size))

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32, copy=False)


class _InMemoryIndex:
    """Simple in-memory cosine similarity fallback when FAISS is not installed."""

    def __init__(self, dim: int):
        self.dim = dim
        self._vectors: list[np.ndarray] = []

    @property
    def ntotal(self) -> int:
        return len(self._vectors)

    def add(self, vecs: np.ndarray) -> None:
        for v in vecs:
            self._vectors.append(v.copy())

    def search(self, query: np.ndarray, k: int):
        if not self._vectors:
            return np.array([[]]), np.array([[]])
        matrix = np.stack(self._vectors)
        scores = (matrix @ query[0]).flatten()
        top_k = min(k, len(scores))
        indices = np.argsort(scores)[::-1][:top_k]
        return scores[indices].reshape(1, -1), indices.reshape(1, -1)
