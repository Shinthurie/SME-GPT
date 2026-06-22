# Component 1 — Semantic OCR Post-Correction

> Adapted from `docs/Research Components sme gpt.pdf` (Research Component 1).
> **Substitution:** the research recommends a QLoRA-fine-tuned Gemma-2-2B; **we use the DeepSeek API**
> for now. The numeric-safeguard logic is model-agnostic, so the model can be swapped later with no
> contract change.

## Purpose

First intelligence layer of ingestion. Runs **after OCR, before layout analysis**. Converts noisy
OCR output from Sinhala–English financial documents into text that is **semantically correct**,
**numerically immutable**, and **bounding-box aligned**.

## Position in pipeline

```
OCR boxes (Surya) → C1 correct each box (DeepSeek) → numeric safeguard → final_safe_boxes.json → C2
```

## Inputs

- `page_images[]` (PNG, 300 DPI)
- `tenant_id`, `document_id`
- raw OCR boxes via `OCRService.run()` (`backend/ocr_service.py`), canonical schema:
  `{ text, bbox:[x1,y1,x2,y2], confidence, label, page }`

### OCR engine reality check (Iteration 2)

Surya shipped a v2 API (`SuryaInferenceManager`, see `docs/suryaREADME.md`) that replaces
the old `text_lines` output with **blocks**: `{label, raw_label, reading_order, html, polygon,
bbox, confidence, skipped, error}` per page, plus `image_bbox`. `html` carries the block content
(`<p>`, `<table>`, `<math>`, ...) instead of plain text.

v2 needs a running `vllm` (NVIDIA + Docker) or `llama.cpp` inference backend. **Neither runs in
our Colab/local setup today** — no GPU Docker on Colab, and llama.cpp has build issues there too.
So there is no real v2 engine wired in yet, and the live pipeline (`document_pipeline.py`) still
runs the old v1 Surya client (`colab_ocr_client.py` / `local_surya_ocr_client.py`, `text_lines`
schema) — untouched by this iteration.

`backend/ocr_service.py` defines the canonical box schema above and a `boxes_from_surya_v2_page()`
adapter (HTML → plain text) so C1 (and later C2) can be built against the **real v2 output shape**
today. `MockSuryaOCRService` loads a hand-authored fixture shaped exactly like Surya's
`results.json` (`backend/sample_docs/invoice_mock_surya_v2.json`) and stands in until a real v2
backend is available — swap it for a real `SuryaV2OCRService` later with no change downstream.

## Output — `final_safe_boxes.json`

```json
{ "page": 1, "boxes": [
  { "text": "ඉන්වොයිස් අංකය", "bbox": [120,80,380,120], "confidence": 0.71,
    "locked_digits": false, "source": "ai_corrected" } ] }
```
Secondary: `raw_ocr_boxes.json`, `ai_corrected_boxes.json`, `plain_text.txt`, `quality_report.json`.

## Correction unit

- Operate **per OCR line/box**, not whole-page blobs. Implemented in `backend/ocr_correction.py`
  (`correct_box`/`correct_pages`), alongside (not replacing) the existing whole-text
  `llm_correction.py` path the live v1 pipeline still uses.
- Preserve the original `bbox`. Correction is **text-only**.

## Numeric safeguard (deterministic, non-negotiable)

A correction is **rejected** (fall back to raw OCR text) if any of these differ between raw and corrected:
1. digit count
2. digit sequence
3. decimal structure

```python
def safe_correct(raw: str, corrected: str) -> tuple[str, str]:
    if extract_digits(raw) != extract_digits(corrected):
        return raw, "raw_ocr"
    if _decimal_skeleton(raw) != _decimal_skeleton(corrected):
        return raw, "raw_ocr"
    return corrected, "ai_corrected"
```

`_decimal_skeleton` catches the case `extract_digits` alone misses: `"500.00"` → `"5000.0"` has
the identical digit sequence (`50000`) but a different decimal point position — a different value.
A `.` only counts as a decimal point when it sits between two digits, so unrelated periods (e.g.
`"Rs."`) don't cause false rejections. Implemented in `backend/ocr_correction.py`, unit-tested in
`backend/tests/test_iter2_ocr_correction.py`.

This guarantees the LLM can never silently change `500.00`.

## Failure handling

| Failure | Behavior |
|---|---|
| LLM/DeepSeek crashes or times out | use raw OCR text (`source="raw_ocr"`) |
| Unsafe numeric change | reject correction, keep raw |
| Low-confidence OCR | prefer AI-corrected text |

## OCR engine — standalone & pluggable

Surya stays behind an `OCRService` interface (`backend/ocr_service.py`, FR-08). C1 consumes its
boxes but is not coupled to it; the engine can be swapped without touching C1. Today that means
`MockSuryaOCRService` (fixture-backed, v2-shaped); the v1 colab/local client keeps serving the
live app unchanged until C1+C2 are ready to be wired into `document_pipeline.py`.

## Quality metrics (see TESTING.md)

- **CER** < 5% (OCR quality)
- **NAR** = 100% (numeric integrity)
- unsafe-block rejection rate (tracked)

## Implementation notes (Iter 2)

- Reuse existing token-masking ideas from `llm_correction.py`, but move to box granularity
  (`backend/ocr_correction.py` imports `preserve_sensitive_tokens`/`call_ollama`/etc. directly
  rather than duplicating them).
- Keep Sinhala (U+0D80–U+0DFF) preserved; never "translate".
- `build_quality_report()` emits the CER/NAR scaffolding. NAR is 1.0 by construction; CER is
  `null` until a ground-truth transcript exists for a sample doc (tracked as a follow-up —
  `backend/tests/fixtures/` per `docs/TESTING.md`).
- **Not yet wired into `document_pipeline.py`** — this iteration ships the box-level module,
  the `OCRService` contract, and the mock fixture as standalone, tested code. Wiring it into the
  live `/process-document` path is deferred until C2 (layout) is ready to consume boxes too,
  since extraction currently expects a single page text blob.
