# Iteration 9 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **Branch:** main

## 1. Scope

Wire C1+C2 into the live document pipeline: after OCR + per-box correction, produce rich
`spatial_chunks.json` via `spatial_serialization.build_spatial_chunks()`, embed and store
chunk vectors in `ChunkEmbedding` on confirm-save, and persist the raw safe-boxes and
spatial-chunks JSON blobs on the `FinancialDocument` row.

Closes **FR-06, FR-07, FR-09, FR-13, FR-14, FR-15, FR-16, FR-17, FR-19, FR-22, FR-23**.

Delivered:
- `backend/document_pipeline.py` — after the existing C2 `serialize_safe_boxes()` block,
  calls `_build_rich_spatial_chunks()` (alias for `spatial_serialization.build_spatial_chunks`)
  with `tenant_id="__pending__"` and `document_id="__pending__"`. Returns `safe_boxes` and
  `rich_spatial_chunks` from both `build_preview_from_versions()` and
  `process_uploaded_document()`.
- `backend/app.py` — `/process-document`: stores `safe_boxes` and
  `rich_spatial_chunks_template` in `PROCESSING_SESSIONS[session_id]["meta"]`.
  `/process-document-stream`: adds inline C1 `correct_boxes_for_page()` + C2
  `build_spatial_chunks()` with the same pending-ID pattern.
  `/confirm-save`: after successful `upsert_confirmed_record()`, patches pending IDs,
  calls `embed_rows(get_embedding_service())` + `upsert_chunk_embeddings()`, then
  persists `safeboxJson` and `spatialChunksJson` via a targeted SQL UPDATE. Embedding
  is best-effort (never blocks the save response on failure).
- `backend/dataset_manager.py` — `safe_boxes_json` and `spatial_chunks_json` added to
  `DATASET_COLUMNS`, `RECORD_TO_DB` (→ `safeboxJson`, `spatialChunksJson`), and
  `normalize_record()`. Stored as TEXT (not JSONB); `_to_db_text()` path.
- `frontend/prisma/schema.prisma` — `safeboxJson String? @db.Text` and
  `spatialChunksJson String? @db.Text` added to `FinancialDocument`.
- `frontend/prisma/migrations/20260624000000_iter9_spatial_blobs/migration.sql` —
  `ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS ...` for both columns.
  Applied to live Supabase via psycopg (Prisma CLI P1017 workaround).

## 2. Tests run

| Command | Result |
|---|---|
| `pytest tests/test_iter9_pipeline_wiring.py -v` | **17 passed** in 38 s |
| `pytest tests/ -q` (full suite) | **224 passed** |

Test breakdown (17 Iter 9 tests):
- C1 pages format: 3 cases (page count, page numbers, box count)
- `build_spatial_chunks()`: 3 cases (keys, tenant/doc IDs, empty pages)
- `flatten_chunks_for_embedding()`: 3 cases (list type, required keys, tenant propagation)
- Guard path: 2 cases (empty safe_boxes → no c1_pages, no build call)
- `normalize_record()`: 4 cases (key presence, NULL default, string preservation)
- DB integration (skip when no DATABASE_URL): 2 cases (column existence, blob round-trip)

## 3. What changes for users

- A document confirmed via `/confirm-save` now automatically:
  1. Generates rich `SpatialChunk`s from the corrected OCR boxes
  2. Embeds each chunk's text with `intfloat/multilingual-e5-small` (384-dim)
  3. Upserts into `ChunkEmbedding` (pgvector, tenant-scoped)
  4. Persists the raw JSON blobs on the `FinancialDocument` row
- `GET /documents/{id}` now returns `safe_boxes_json` and `spatial_chunks_json` fields
  (null for documents saved before this iteration).

## 4. Known gaps

- Embedding uses `intfloat/multilingual-e5-small` (sentence-transformers), which requires
  PyTorch (~2 GB). Not installed in CI — the `LocalMultilingualEmbeddingService` import is
  lazy (inside `embed_rows()`) so collection-time import still works. A CI-safe fallback
  would be to check if sentence-transformers is available before calling `get_embedding_service()`.
- The streaming endpoint (`/process-document-stream`) now runs C1 per-box correction inline
  which adds latency. For a fast-path, the box correction could be moved to a background thread.
- `GET /documents/{id}` returns the full JSON blobs as strings; the frontend
  `DocumentDetail` type does not yet declare `spatial_chunks_json`. That's Iteration 10.

## 5. Next

- Iteration 10: `BboxOverlayViewer` component — parse `spatial_chunks_json` from the API
  and draw SVG rectangles over the document image.
