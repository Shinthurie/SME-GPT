# Iteration 4 — Test Report

**Date:** 2026-06-22 · **Owner(s):** Ashfak (backend/AI) · **PR:** (feat/iter-4-vector-retrieval)

## 1. Scope

Indexing & Vector Retrieval (RAG) over Component 2's `spatial_chunks.json`: embed each
`SpatialChunk.text`, store it in pgvector with tenant/document/chunk/bbox metadata, and retrieve
top-k chunks by cosine similarity with provenance intact (FR-14…17).

Delivered:
- `backend/embedding_service.py` — pluggable `EmbeddingService` (DeepSeek has no embeddings
  endpoint, so this mirrors `OCRService`'s pattern): `HashingEmbeddingService` (deterministic
  bag-of-words hashing, no model/network — used by the test suite) and
  `LocalMultilingualEmbeddingService` (real default, wraps sentence-transformers'
  `intfloat/multilingual-e5-small`, 384-dim, CPU-friendly, mC4-trained so it covers Sinhala).
- `backend/vector_index.py` — `flatten_chunks_for_embedding()` (pure, `build_spatial_chunks()`
  output → embeddable rows), `embed_rows()`, `rank_embedded_rows()` (pure cosine-similarity
  ranking, doubles as the DB-free retrieval-hit-rate harness), `upsert_chunk_embeddings()` and
  `retrieve_top_k()` (pgvector-backed, tenant-filtered, optional document scope).
- `docs/design/iter-4-schema.md` — schema proposal (mirrors `docs/design/iter-1-schema.md`'s
  style): `ChunkEmbedding` table, `vector(384)` column via Prisma's `Unsupported` type, HNSW
  cosine-distance index, RLS enabled (verified live that every other table has
  `relrowsecurity=true` with zero policies — app-layer access control via the backend's
  privileged `DATABASE_URL` connection, which bypasses RLS as table owner). **Applied** to the
  real Supabase instance via `npx prisma migrate deploy`
  (`frontend/prisma/migrations/20260622150000_iter4_chunk_embeddings/`).
- `backend/requirements.txt`: added `pgvector` (lightweight psycopg adapter) and
  `sentence-transformers` (real embedding model; pulls in `torch`).
- `backend/tests/test_iter4_vector_index.py` — 12 tests.
- Docs updated: `docs/ROADMAP.md`, `docs/gap-analysis.md` (FR-14…19 → 🟡), `docs/ARCHITECTURE.md`
  (current-state table, new "Vector embeddings" canonical-artifact section).

**Not done this iteration (by design, same as C1/C2):** wiring retrieval into a FastAPI endpoint
or into an answer-generation flow. There's also no real document to retrieve from yet — C1/C2
aren't wired into `document_pipeline.py`, so today this only runs against the mock OCR fixture and
hand-built rows in tests.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **55 passed** (6 iter-1 DB + 16 iter-2 + 21 iter-3 + 12 iter-4) |
| `cd backend && ruff check ocr_service.py spatial_serialization.py embedding_service.py vector_index.py tests/` | pass |
| `cd frontend && npx prisma validate` | pass |
| `cd frontend && npx prisma migrate deploy` | applied cleanly against live Supabase |

New tests cover:
- `HashingEmbeddingService`: deterministic (same text → same vector), unit-normalized, empty text
  → zero vector.
- `get_embedding_service()`: `"hashing"` engine resolves correctly; unknown engine raises
  `NotImplementedError` (mirrors `ocr_service.get_ocr_service`).
- `flatten_chunks_for_embedding`: row count matches total chunk count, provenance
  (tenant/document/page/bbox) preserved per row.
- `rank_embedded_rows`: orders by cosine similarity descending, respects `k`, strips the raw
  `embedding` vector from ranked output (keeps `similarity` instead).
- **Retrieval hit-rate harness** (ROADMAP's explicit ask): 5 labelled `(query, expected substring)`
  pairs against the mock fixture's `spatial_chunks.json` — top-1 result matches expectation for
  all 5 (`hit_rate == 1.0`). One query (`"රැවුල කැපිමට"`) specifically discriminates between two
  near-identical line items (`"කොණ්ඩෙය කැපිමට (...)"` vs `"රැවුල කැපිමට"`), since both share most
  tokens — exercising real per-chunk discrimination, not just trivial keyword presence.
- **Naive-baseline comparison**: per-chunk retrieval returns one line item's worth of text for a
  query; a whole-document-blob baseline (the closest analogue to pre-C2 behavior — no chunking at
  all) always returns the same oversized blob regardless of query, so it can never narrow to a
  specific bbox/line item. Demonstrates `docs/TESTING.md`'s "beats naive chunking baseline" framing
  concretely, ahead of C4's formal version of this metric in Iteration 6.
- **Live Supabase round trip**: `upsert_chunk_embeddings()` then `retrieve_top_k()` against the
  real `ChunkEmbedding` table — correct top-1 chunk + bbox returned, and tenant isolation verified
  (tenant B's query against tenant A's data returns zero rows). Skipped automatically when
  `DATABASE_URL` is unset (same pattern as `tests/test_iter1_data_layer.py`); ran and passed here
  against the real Supabase instance, with the test's own rows cleaned up in a `finally` block.

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Retrieval hit-rate (labelled queries) | beats naive chunking baseline | **5/5 (100%)** top-1 hit rate on the labelled set, using the deterministic hashing embedding (lexical-overlap proxy, not real semantic similarity — see gaps below) |
| Provenance success rate (valid bbox per result) | high | **100%** — every `retrieve_top_k`/`rank_embedded_rows` result carries its source chunk's exact `page`/`bbox` |
| Tenant isolation | required (NFR-15) | **verified** — live DB round-trip test confirms tenant B retrieves zero rows from tenant A's index |

## 4. Failures / known gaps

- **`LocalMultilingualEmbeddingService` (the real model) is untested in CI** — same status as C1's
  real Surya v2 engine. `sentence-transformers`/`torch` are in `requirements.txt` but no test
  exercises the real model (would require a model download in CI); only `HashingEmbeddingService`
  is exercised. The hit-rate numbers above measure pipeline correctness (ranking math, provenance,
  tenant filtering), not real semantic retrieval quality — that needs a follow-up smoke test once
  the dependency is actually installed and exercised manually.
- **No FastAPI endpoint or C3 wiring yet** — `vector_index.py` is a standalone, tested module, same
  pattern as C1/C2.
- **RLS has no policies** (same as every other table) — access control is entirely at the app
  layer via the backend's privileged DB connection. If the frontend ever queries Postgres directly
  via Supabase's anon/authenticated PostgREST role instead of going through the backend, this table
  (like all the others) would need real policies added.
- **Cascade delete not wired** — `DELETE /documents/{id}` doesn't yet delete matching
  `ChunkEmbedding` rows (no FK; tracked in `docs/design/iter-4-schema.md` open question #3).

## 5. Next

- Iteration 5 (Component 3 — Neuro-Symbolic PAL Arithmetic QA): wire `retrieve_top_k()` into the
  planner/retriever step, replace `ai_helper.py`/`data_tools.py`'s ad-hoc logic.
- Manually verify `LocalMultilingualEmbeddingService` end-to-end once `sentence-transformers` is
  installed (real semantic retrieval quality, not just pipeline correctness).
- Revisit wiring C1+C2+C4 into `document_pipeline.py` so there's a real document to embed/retrieve
  from, rather than only the mock fixture.
- Add `ChunkEmbedding` cleanup to the document-delete flow once wired in.
