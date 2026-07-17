"""Optional cross-encoder reranker for RAG (retrieval-quality layer).

A bi-encoder (embedding_service) is fast but coarse: it scores query and chunk
independently. A cross-encoder scores the (query, chunk) PAIR jointly, which is
markedly more precise -- at the cost of running the model once per candidate, so
it adds latency. It is therefore OFF by default and gated behind RAG_RERANK=true;
when off, rerank() is an identity pass-through (candidates returned unchanged).

Pluggable + lazy-loaded, exactly like embedding_service.py: importing this module
never downloads a model, and the tests use the pass-through (flag off) so the
suite stays hermetic. Model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
(multilingual, supports Sinhala) by default; override with RAG_RERANK_MODEL.
"""
from __future__ import annotations

import os

_DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
_model = None


def rerank_enabled() -> bool:
    return os.getenv("RAG_RERANK", "false").strip().lower() == "true"


def _load():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(os.getenv("RAG_RERANK_MODEL", _DEFAULT_MODEL))
    return _model


def rerank(query: str, candidates: list[dict], top_k: int, text_key: str = "text") -> list[dict]:
    """Reorder `candidates` by cross-encoder relevance to `query` and return the
    top_k. No-op (returns candidates[:top_k]) when RAG_RERANK is off or on any
    failure -- reranking is a best-effort precision boost, never a hard
    dependency of retrieval."""
    if not candidates:
        return []
    if not rerank_enabled():
        return candidates[:top_k]
    try:
        model = _load()
        pairs = [(query, c.get(text_key, "")) for c in candidates]
        scores = model.predict(pairs)
        ranked = sorted(
            zip(candidates, scores), key=lambda cs: float(cs[1]), reverse=True
        )
        out = []
        for cand, score in ranked[:top_k]:
            out.append({**cand, "rerank_score": float(score)})
        return out
    except Exception as exc:
        print(f"[RAG] reranker unavailable ({exc}); using retrieval order.", flush=True)
        return candidates[:top_k]
