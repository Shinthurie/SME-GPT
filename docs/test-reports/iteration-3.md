# Iteration 3 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **Branch:** main

## 1. Scope

Component 2 — Layout-Aware Spatial Serialization: row clustering, header detection,
header→row binding, and template-based chunk classification producing `spatial_chunks.json`.

Also fixed: Supabase connection for the frontend (Prisma `PrismaPg` adapter).

### Supabase / frontend fix
- `frontend/.env` — `DATABASE_URL` changed to port 6543 (PgBouncer transaction mode);
  removed spaces around `=` and the `?sslmode=require` that `pg` v8 escalates to
  `verify-full` (rejecting Supabase's AWS certificate chain).
- `frontend/src/lib/prisma.ts` — creates `pg.Pool` with `ssl:{rejectUnauthorized:false}`
  and passes the pool to `PrismaPg`; bypasses pg v8 certificate verification regression.
- `frontend/prisma.config.ts` — appends `?sslmode=require` for the Prisma CLI (which
  uses its own Rust TLS engine that trusts the Supabase cert).

### Spatial serializer (`backend/spatial_serializer.py`)
- `cluster_rows_by_y(boxes, gap_threshold=None)` — dynamic y-axis threshold (1.5 × median
  inter-center gap, min 5 px); rows sorted left-to-right.
- `is_header_row(row)` — English/Sinhala keyword lookup + all-caps single-word heuristic.
- `classify_row(row, is_header)` — Header | KeyValue (2 boxes) | LineItem (3+ boxes with
  digit) | Text.
- `bind_to_nearest_header(x_center, header_chunks)` — x-center nearest-header binding.
- `merge_bboxes(boxes)` — enclosing [x1,y1,x2,y2] for all boxes in a row.
- `serialize_safe_boxes(safe_boxes_by_page)` — end-to-end: produces flat list of
  SpatialChunk dicts with token_ids (page-local provenance) and header_ref.

### Pipeline integration
- `document_pipeline.py` imports `serialize_safe_boxes` and, after per-box correction,
  writes `temp_processing/spatial_chunks.json`.
- Preview dict now includes `spatial_chunks` alongside `safe_boxes`.

## 2. Tests run

| Command | Result |
|---|---|
| `python -m pytest tests/test_c2_spatial_serializer.py -v` | **36 passed** in 0.08 s |
| `python -m pytest tests/ -v` (full suite) | **75 passed** in 146 s |

Component 2 tests cover:
- `cluster_rows_by_y`: 6 cases (empty, single, two rows, LR sort, dynamic threshold, all-same)
- `is_header_row`: 7 cases (EN keywords, table header keywords, all-caps, non-header, number-only, Sinhala)
- `classify_row`: 5 cases (Header, KeyValue, LineItem, Text-single, Text-multi-no-number)
- `bind_to_nearest_header`: 3 cases (no headers, single, nearest of two)
- `merge_bboxes`: 3 cases (single, multiple, empty)
- `serialize_safe_boxes`: 12 cases (list type, schema, unique IDs, page index, header/non-header refs, token_id types/bounds, bbox validity, empty input, multi-page, text concatenation)

## 3. Metrics

- All 36 C2 tests pure Python (no DB/LLM/OCR) — run in CI with no secrets.
- Existing 33 C1 + 6 iter-1 + 1 smoke tests unaffected.

## 4. Known gaps

- Header detection is keyword-based; a table header without a known keyword (e.g.
  purely Sinhala labels not in the dictionary) will be missed.  Expanding the Sinhala
  keyword set and adding a "multi-column numeric row" heuristic are follow-ups.
- `classify_row` KeyValue rule (exactly 2 boxes) misclassifies 2-column line items.
  A positional / column-alignment check is deferred to a refinement pass.
- CER/NAR evaluation on real `sample_docs/` still pending (no labelled ground truth).

## 5. Next

- Iteration 4 (Indexing & Vector Retrieval): embed `SpatialChunk.text` into pgvector
  with metadata (tenant/doc/chunk/bbox); retrieval API (top-k + provenance).
