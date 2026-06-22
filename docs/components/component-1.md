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
- raw OCR boxes: `{ text, bbox:[x1,y1,x2,y2], confidence }`

## Output — `final_safe_boxes.json`

```json
{ "page": 1, "boxes": [
  { "text": "ඉන්වොයිස් අංකය", "bbox": [120,80,380,120], "confidence": 0.71,
    "locked_digits": false, "source": "ai_corrected" } ] }
```
Secondary: `raw_ocr_boxes.json`, `ai_corrected_boxes.json`, `plain_text.txt`, `quality_report.json`.

## Correction unit

- Operate **per OCR line/box**, not whole-page blobs (this is the main refactor from today's
  `llm_correction.py`).
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
    return corrected, "ai_corrected"
```

This guarantees the LLM can never silently change `500.00`.

## Failure handling

| Failure | Behavior |
|---|---|
| LLM/DeepSeek crashes or times out | use raw OCR text (`source="raw_ocr"`) |
| Unsafe numeric change | reject correction, keep raw |
| Low-confidence OCR | prefer AI-corrected text |

## OCR engine — standalone & pluggable

Surya (Colab remote → local fallback) stays behind an `OCRService` interface (FR-08). C1 consumes
its boxes but is not coupled to it; the engine can be swapped without touching C1.

## Quality metrics (see TESTING.md)

- **CER** < 5% (OCR quality)
- **NAR** = 100% (numeric integrity)
- unsafe-block rejection rate (tracked)

## Implementation notes (Iter 2)

- Reuse existing token-masking ideas from `llm_correction.py`, but move to box granularity.
- Keep Sinhala (U+0D80–U+0DFF) preserved; never "translate".
- Emit `quality_report.json` for the eval harness.
