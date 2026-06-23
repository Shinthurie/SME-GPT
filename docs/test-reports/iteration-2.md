# Iteration 2 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie (implementation) · **Branch:** main

## 1. Scope

Component 1 — Semantic OCR Post-Correction: box-level safe correction with numeric
immutability, pluggable OCR service interface, and quality metric scaffolding.

Delivered:
- `llm_correction.py` — added `extract_digit_sequences`, `safe_correct`, `correct_box`,
  `correct_boxes_for_page`, `compute_cer`, `compute_nar`
- `ocr_service.py` — new `OCRService` ABC + `ColabOCRService`, `LocalSuryaOCRService`,
  `get_ocr_service()` factory (FR-08)
- `document_pipeline.py` — uses `get_ocr_service()` (removes direct Colab/Surya calls);
  applies `correct_boxes_for_page()` after OCR selection; writes
  `temp_processing/final_safe_boxes.json` per document; returns `safe_boxes` in preview
- `db.py` — fixed `prepare_threshold=None` for Supabase PgBouncer transaction-mode pooler
- `backend/.env` — fixed DATABASE_URL format (port 5432→6543, sslmode=require, no spaces
  around `=`); fixed dotenv parse regression

## 2. Tests run

| Command | Result |
|---|---|
| `python -m pytest tests/test_c1_numeric_safeguard.py -v` | **33 passed** in 0.08 s |
| `python -m pytest tests/ -v` (full suite) | **39 passed** in 148 s |

Component 1 tests cover:
- `extract_digit_sequences`: 6 cases (basic, empty, None, no digits, single group, multi-group)
- `safe_correct`: 8 cases (accepts match, rejects value change, rejects dropped/added digit, allows pure text fix, no-op, None inputs)
- `correct_box`: 6 cases (required keys, locked digits, digit invariant, source field, bbox/confidence passthrough, empty text)
- `correct_boxes_for_page`: 4 cases (count, empty list, None, digit preservation across page)
- `compute_cer`: 5 cases (identical, different, one substitution, empty original, both empty)
- `compute_nar`: 4 cases (all preserved, none preserved, half preserved, empty input)

DB integration tests (6) still passing against Supabase.

## 3. Metrics

- **NAR (design target):** 100% — `safe_correct()` guarantees rejection of any correction
  that would alter a digit sequence.  Verified by unit test (`test_correct_box_never_changes_digits`).
- **CER scaffolding:** implemented; production eval on `sample_docs/` deferred to a
  follow-up once sample labelled ground-truth exists.

## 4. Failures / known gaps

- Per-box LLM correction (one DeepSeek call per box) is not implemented; boxes are
  corrected with dictionary + SymSpell only.  Full LLM-per-box is expensive (~100+ calls
  per document) and is deferred pending batching strategy.
- `final_safe_boxes.json` is written to `temp_processing/` (cleared between runs).
  Persistent storage per document is deferred to Iteration 4 (vector indexing).
- CER eval on real `sample_docs/` not yet run (no labelled ground truth available).

## 5. Next

- Iteration 3 (Component 2): layout-aware spatial serialisation — row clustering,
  header detection, `spatial_chunks.json` using the `final_safe_boxes.json` as input.
