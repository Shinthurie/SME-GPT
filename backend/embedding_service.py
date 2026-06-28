"""Embeddings for Component-2 SpatialChunks (Iteration 4 — vector indexing & retrieval).

DeepSeek (the project's LLM, see docs/ARCHITECTURE.md) has no embeddings endpoint, so this is a
separate, pluggable EmbeddingService (FR-14), mirroring `ocr_service.py`'s `OCRService` pattern.

Two implementations:
- `HashingEmbeddingService` — deterministic, dependency-free bag-of-words hashing vector. No
  network, no model download -> used by tests so the suite stays hermetic and fast (same reasoning
  as monkeypatching DeepSeek in ocr_correction tests). Good enough for lexical-overlap ranking,
  not real semantic similarity.
- `LocalMultilingualEmbeddingService` — the real implementation, wraps sentence-transformers'
  `intfloat/multilingual-e5-small` (384-dim, CPU-friendly, trained on mC4's 100+ languages
  including Sinhala — see docs/design/iter-4-schema.md decision #3). Lazy-loaded so importing this
  module never triggers a model download; untested in CI for the same reason MockSuryaOCRService
  stands in for a real OCR engine (no network/model download in the test suite).

e5 models are asymmetric: embed queries with the `"query: "` prefix and documents/chunks with
`"passage: "` (see the model card). Both implementations accept `mode` for API symmetry even
though only the real model's output changes with it.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from abc import ABC, abstractmethod

# Quieten Hugging Face when loading the embedding model from the local cache:
# - no per-load "Loading weights" progress bar
# - no "you are sending unauthenticated requests to the HF Hub / set HF_TOKEN"
#   advisory (we only ever read an already-cached model, never download).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

EMBEDDING_DIM = 384


class EmbeddingService(ABC):
    @abstractmethod
    def embed(self, texts: list[str], mode: str = "passage") -> list[list[float]]:
        """mode: "passage" for chunks being indexed, "query" for search queries."""
        raise NotImplementedError


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class HashingEmbeddingService(EmbeddingService):
    """Deterministic bag-of-words hashing embedding (no model, no network).

    Each token is hashed into one of `dim` buckets; the resulting vector is
    L2-normalized so cosine similarity behaves like a real embedding for
    ranking tests, without needing a real model. `mode` is accepted but
    ignored — there's no asymmetric query/passage distinction without a real
    model to exploit it.
    """

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def embed(self, texts: list[str], mode: str = "passage") -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall((text or "").lower()):
            idx = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class LocalMultilingualEmbeddingService(EmbeddingService):
    """Real embedding model: `intfloat/multilingual-e5-small` via
    sentence-transformers. Lazy-loaded on first `embed()` call so importing
    this module (or `get_embedding_service()` with a different engine) never
    requires the model to be downloaded."""

    MODEL_NAME = "intfloat/multilingual-e5-small"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str], mode: str = "passage") -> list[list[float]]:
        model = self._load()
        prefix = "query: " if mode == "query" else "passage: "
        prefixed = [prefix + (t or "") for t in texts]
        embeddings = model.encode(prefixed, normalize_embeddings=True)
        return [vec.tolist() for vec in embeddings]


# Cache one service instance per engine. The real model holds the loaded
# SentenceTransformer in `self._model`, so reusing the instance means the model
# is loaded ONCE per process instead of on every call (e.g. every /ask-query
# RAG step previously reloaded ~200MB of weights). Services are stateless aside
# from the cached model, so sharing them is safe.
_SERVICE_CACHE: dict[str, EmbeddingService] = {}


def get_embedding_service(engine: str | None = None) -> EmbeddingService:
    """Factory mirroring `ocr_service.get_ocr_service()`. Defaults to the real
    model ('local_multilingual') since, unlike Surya v2, embedding inference
    has no GPU/infra blocker. Returns a cached singleton per engine so the model
    loads only once. Tests construct `HashingEmbeddingService` directly rather
    than going through this factory's default."""
    engine = (engine or "local_multilingual").strip().lower()

    cached = _SERVICE_CACHE.get(engine)
    if cached is not None:
        return cached

    if engine == "local_multilingual":
        service: EmbeddingService = LocalMultilingualEmbeddingService()
    elif engine == "hashing":
        service = HashingEmbeddingService()
    else:
        raise NotImplementedError(f"Embedding engine '{engine}' is not supported.")

    _SERVICE_CACHE[engine] = service
    return service
