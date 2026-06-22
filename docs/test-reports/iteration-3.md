# Iteration 3 — Test Report

**Date:** 2026-06-22 · **Owner(s):** Ashfak (backend/AI) · **PR:** (feat/iter-3-spatial-serialization)

## 1. Scope

Component 2 (layout-aware spatial serialization), built deterministically (no LLM) over the same
canonical `OCRService` box schema C1 (Iteration 2) introduced, consuming the `final_safe_boxes.json`
shape C1 produces.

Delivered:
- `backend/spatial_serialization.py` — `cluster_rows` (y-axis row clustering, dynamic threshold),
  `detect_header_row` (English + Sinhala keyword matching, word-boundary anchored),
  `bind_row_to_headers` (x-axis nearest-center binding, `unknown_column_N` fallback),
  `classify_key_value` (`Key: Value` pattern), `serialize_header` / `serialize_line_item_row` /
  `serialize_line_item_block` / `serialize_key_value` / `serialize_section_text` (the four
  templates from component-2.md), and `build_spatial_chunks()` — the top-level entry point that
  emits the exact `spatial_chunks.json` schema (tenant_id/document_id/version/language_hint/pages,
  each chunk with chunk_id/chunk_type/text/fields/provenance/quality/metadata).
- `backend/ocr_service.py` change (shared with C1): `Table` blocks are now expanded into per-cell
  canonical boxes (`table_block_to_cell_boxes`, `_parse_html_table_rows`) instead of being
  flattened into one text blob. Surya v2 gives one bbox per table, but C2's row-clustering
  algorithm needs per-token geometry — cell bboxes are synthesized via a uniform grid over the
  table block's bbox, with `table_id`/`row_index`/`col_index` carried on each cell box.
- `backend/tests/test_iter3_spatial_serialization.py` — 21 unit/end-to-end tests.
- `backend/tests/test_iter2_ocr_correction.py` updated: the mock fixture's expected box count
  changed from 10 to 21 (1 table block -> 12 cell boxes) because of the `ocr_service.py` change
  above; all other Iteration 2 assertions are unaffected and still pass.
- Docs updated: `docs/components/component-2.md` (implementation notes: table-cell-expansion
  rationale, word-boundary keyword matching, unmapped-header fallback behavior, known
  multi-table-per-page limitation), `docs/ROADMAP.md` (Iteration 3 boxes ticked + follow-ups),
  `docs/gap-analysis.md` (FR-09/10/11/12/13 and C2 row updated to 🟡).

**Not done this iteration (by design, same as C1):** wiring C1+C2 into `document_pipeline.py` /
`/process-document`. The live pipeline still runs the unmodified v1 Surya client and the
whole-page-text extraction flow; replacing it is deferred to a later iteration once a real OCR
engine exists.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **43 passed** (6 iter-1 DB tests + 16 iter-2 + 21 iter-3) |
| `cd backend && ruff check ocr_service.py spatial_serialization.py tests/test_iter3_spatial_serialization.py tests/test_iter2_ocr_correction.py` | pass |

No network/DB access is required for the iter-2/iter-3 tests — DeepSeek calls remain monkeypatched
in iter-2, and C2 has no LLM dependency at all (deterministic by design).

New tests cover:
- `cluster_rows`: groups boxes by y-alignment, orders within a row by x, dynamic
  `median(text_height) * alpha` threshold correctly separates distinct rows, empty input.
- `detect_header_row`: English keyword row, Sinhala keyword row, returns `(None, [])` when no row
  scores ≥ 0.5 keyword density (verifies the word-boundary fix — `"no."` no longer false-positives
  inside `"now"`).
- `bind_row_to_headers`: nearest x-center assignment, `unknown_column_N` fallback with no headers,
  duplicate-nearest-header disambiguation (second box falls back to `unknown_column`).
- `classify_key_value`: matches `Key: Value`, rejects multi-box rows, rejects text without a colon.
- `build_spatial_chunks`: top-level schema fields present; **never-drops-tokens** invariant on the
  mock fixture (sum of `token_bboxes` across all emitted chunks == input box count, 21); correct
  line-item extraction (totals `600/400/300` bound to the `total` field, `locked_digits=True`,
  `header_bound=True`); KeyValue extraction (`Order ID: 8`, `Date: ...`); `language_hint` detects
  both `en` and `si`; no-header-detected fallback emits positional `unknown_column_N` rows without
  dropping tokens.
- Chunking strategy (component-2.md "Chunking strategy"): exactly one `line_item_row` chunk per
  row at `row_count == 30` (the `≤30` boundary), and `line_item_block` chunks of 1-10 rows (here:
  8) with the header line repeated in `text` when `row_count == 40`; total rows across blocks
  reconciles to the input row count in both cases.

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Schema validity | 100% | **100%** — every chunk emitted by `build_spatial_chunks` (including the no-header fallback path) carries `chunk_id/chunk_type/text/provenance.page/provenance.bbox/metadata.source_component`, asserted per-chunk in `test_build_spatial_chunks_never_drops_tokens_on_mock_fixture` |
| Cell-extraction accuracy | tracked | **3/3** line items correctly bound on the mock fixture (`600`, `400`, `300` -> `total`; descriptions -> `සේවාව`/fallback key) |
| Association accuracy (number ↔ correct header) | tracked | **100%** on the mock fixture's single table — verified by exact-value assertions in `test_build_spatial_chunks_extracts_line_items_with_correct_values` |
| Never-drop-tokens | 100% | **100%** — guaranteed by construction (every classified row/box always emits a chunk; verified via the token-count reconciliation test) |

## 4. Failures / known gaps

- **Cell bboxes inside a table are synthetic** (uniform grid over the table block's bbox), not
  real per-cell coordinates — Surya v2 doesn't expose those. Acceptable for provenance/UI
  highlighting at "this is roughly where the cell is" granularity, not pixel-exact.
- **Row clustering runs across the whole page, not per `table_id`.** Works correctly for the
  mock fixture (one table per page) but would need to cluster per-table first if two tables ever
  share a y-range on the same page. Tracked as a follow-up in `docs/ROADMAP.md`.
- **Canonical-field mapping is incomplete by design** — component-2.md's Sinhala keyword list
  doesn't cover every header term that appears in real documents (e.g. `සේවාව` "service" in the
  mock fixture). Unmapped headers fall back to using their own text as the field key rather than
  `unknown_column`, which preserves more information but means downstream consumers (C3) need to
  handle field keys that aren't in the canonical list.
- **C2 not wired into the live app** — same status as C1. No user-facing behavior changed this
  iteration.
- `MockSuryaOCRService` is still the only OCR source (no real Surya v2 engine) — metrics above are
  pipeline-correctness checks against a hand-authored fixture, not accuracy numbers against real
  scanned documents.

## 5. Next

- Iteration 4 (Indexing & Vector Retrieval): embed `SpatialChunk.text` into pgvector, build the
  retrieval API with provenance.
- Revisit wiring C1+C2 into `document_pipeline.py` once a real OCR engine (vllm/llama.cpp-backed
  Surya v2) is runnable, replacing the live whole-text-blob extraction flow end-to-end.
- Per-`table_id` row clustering if/when multi-table-per-page documents need support.
- Expand the canonical-field keyword list as more real document headers are observed.
