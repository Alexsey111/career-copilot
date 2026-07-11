# app/services/embedding_service.py

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

USE_REAL_MODEL = os.getenv("USE_REAL_EMBEDDING_MODEL", "false").lower() == "true"


def _get_model():
    if not USE_REAL_MODEL:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBEDDING_MODEL)
    except ImportError:
        logger.warning("sentence-transformers not installed, using hash-based fallback")
        return None
    except Exception as e:
        logger.warning(f"Failed to load model: {e}, using hash-based fallback")
        return None


@lru_cache(maxsize=1)
def _cached_model():
    return _get_model()


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            self._model = _cached_model()

    def embed_text(self, text: str) -> list[float]:
        self._ensure_model()

        if self._model is not None:
            try:
                embedding = self._model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
            except Exception:
                logger.warning("embedding_model_failed, falling back to hash embedding")

        return self._hash_embed(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_model()

        if self._model is not None:
            try:
                embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
                return [e.tolist() for e in embeddings]
            except Exception:
                logger.warning("batch_embedding_failed, falling back to hash embedding")

        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str) -> list[float]:
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        tokens = text.lower().split()
        for i, token in enumerate(tokens):
            token_hash = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
            idx = token_hash % EMBEDDING_DIM
            vector[idx] += 1.0

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    def similarity(self, a: list[float], b: list[float]) -> float:
        a_arr = np.array(a, dtype=np.float64)
        b_arr = np.array(b, dtype=np.float64)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
