# Iteration 2 — Test Report

**Date:** 2026-06-22 · **Owner(s):** Ashfak (backend/AI) · **PR:** (feat/iter-2-ocr-correction)

## 1. Scope

Component 1 (semantic OCR post-correction), built box-level and against the real Surya v2 output
shape, using mock data since no Surya v2 inference backend is runnable yet.

Delivered:
- `backend/ocr_service.py` — canonical OCR box schema (`text, bbox, confidence, label, page`),
  `OCRService` ABC (FR-08), `boxes_from_surya_v2_page()` HTML→text adapter, `MockSuryaOCRService`,
  and a `get_ocr_service()` factory.
- `backend/sample_docs/invoice_mock_surya_v2.json` — hand-authored fixture shaped exactly like
  Surya v2's `results.json` (`blocks` with `label/raw_label/reading_order/html/polygon/bbox/
  confidence/skipped/error` + `image_bbox`), modeled on the real `backend/sample_docs/invoice.png`
  receipt, with deliberate OCR-style errors injected (e.g. `"07726920S7"`, `"Toatl"`,
  `"Cach retrun"`) to exercise correction and the numeric safeguard.
- `backend/ocr_correction.py` — box-level C1 module: `extract_digits`, `_decimal_skeleton`,
  `safe_correct()` (the numeric-immutability safeguard), `correct_box`/`correct_pages`,
  `write_final_safe_boxes()`, `build_quality_report()`. Reuses `llm_correction.py`'s
  token-masking/DeepSeek-call helpers rather than duplicating them; does not touch or replace the
  live whole-text correction path the v1 pipeline still uses.
- `backend/tests/test_iter2_ocr_correction.py` — 16 unit tests.
- Docs updated: `docs/components/component-1.md` (Surya v2 reality + infra blocker, updated
  `safe_correct` spec including the decimal-skeleton check, "not yet wired" note),
  `docs/ROADMAP.md` (Iteration 2 boxes ticked + follow-ups).

**Not done this iteration (by design):** wiring C1 into `document_pipeline.py` /
`/process-document`. Extraction (`ocr_to_json_extractor.py`) currently consumes one page-text
blob; rewiring it to consume per-box output is a C2 (layout serialization) concern and is
deferred so this iteration doesn't destabilize the live app. The production pipeline still runs
the old Surya v1 client unchanged.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **22 passed** (6 prior iter-1 DB tests + 16 new) |
| `cd backend && ruff check ocr_service.py ocr_correction.py tests/test_iter2_ocr_correction.py` | pass |

New tests cover:
- `safe_correct()`: accepts identical digits, accepts pure-text corrections (no digits), rejects
  changed digit count, rejects changed digit sequence, rejects decimal-structure change
  (`"500.00"` → `"5000.0"`), ignores thousands-separator-only changes (`"1300"` → `"1,300"`).
- `html_block_to_text()`: strips tags/entities, flattens table rows to text.
- `MockSuryaOCRService`: loads the fixture, correct box count (10 text boxes; 1 `Picture` block
  correctly skipped), every box carries `bbox`/`confidence`/`page`.
- `get_ocr_service()`: default mock works; unknown engine raises `NotImplementedError`.
- `correct_pages()` with DeepSeek mocked to fail → deterministic raw-OCR fallback, bbox/text
  preserved exactly.
- `correct_box()` with DeepSeek mocked to *corrupt* a number (`"Total 600"` → `"Total 999999"`)
  → safeguard still rejects and keeps the raw digits (the core invariant).
- `write_final_safe_boxes()` schema validation (every box has
  `text/bbox/confidence/locked_digits/source`).
- `build_quality_report()`: `numeric_accuracy_rate == 1.0` always; box counts reconcile.

DeepSeek calls are monkeypatched in every test that needs determinism, so the suite needs no
network access or live API key — it ran clean against the global Python 3.13 install (no
backend `venv`; see the iteration-1 report's note that the local venv is broken and needs
recreating).

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| NAR (numeric accuracy rate) | = 100% | **100%** (guaranteed by `safe_correct()`, verified by `test_correct_pages_never_alters_digits_even_when_deepseek_corrupts_them`) |
| CER (character error rate) | < 5% | not measured — no ground-truth transcript exists yet for `sample_docs/invoice.png`; `build_quality_report()` reports `null` until one is added |
| unsafe-block rejection rate | tracked | tracked per-box via `source: "raw_ocr"`; not yet run against a real OCR engine (mock fixture only) |

## 4. Failures / known gaps

- **No real Surya v2 engine.** v2 needs a running `vllm` (NVIDIA+Docker) or `llama.cpp` backend;
  neither works in our Colab/local setup today. `MockSuryaOCRService` is a faithful schema
  stand-in, not real OCR — metrics above are pipeline-correctness checks, not accuracy numbers
  against real documents.
- **CER unmeasured** — needs a ground-truth transcript fixture (`backend/tests/fixtures/`), not
  created this iteration.
- **C1 not wired into the live app** — `/process-document` still runs the unmodified v1
  colab/local pipeline. No user-facing behavior changed this iteration.
- `docs/CONTRIBUTING.md` still documents "1 approving review required" / protected `main`, which
  no longer matches the team's current practice (ruleset disabled, self-merge). Not updated this
  iteration — flagged for a follow-up docs PR.

## 5. Next

- Iteration 3 (Component 2): layout-aware spatial serialization, consuming the same canonical
  `OCRService` box schema this iteration introduced — row clustering, header binding,
  `spatial_chunks.json`.
- Once C2 lands, revisit wiring C1+C2 into `document_pipeline.py` to replace the v1
  whole-text-blob flow end-to-end.
- Add a ground-truth transcript fixture to start measuring real CER.
- Reconcile `CONTRIBUTING.md` with the team's current self-merge workflow.
