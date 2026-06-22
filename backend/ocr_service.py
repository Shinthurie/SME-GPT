"""OCRService — pluggable interface around the OCR engine (Surya).

Canonical box schema (independent of OCR engine/version), one per detected box:
    {"text": str, "bbox": [x1, y1, x2, y2], "confidence": float, "label": str, "page": int}

Surya is kept standalone/pluggable per the project's locked decision: C1 (semantic
OCR correction, see ocr_correction.py) consumes only this canonical schema and never
imports Surya directly.

Status (iteration 2):
- The live pipeline (`document_pipeline.py`) still runs the older Surya v1 API
  (`text_lines`, via `colab_ocr_client.py` / `local_surya_ocr_client.py`) and is
  untouched by this module.
- Surya v2 (`SuryaInferenceManager`, block/HTML output — see docs/suryaREADME.md)
  is the schema this module targets going forward, but it needs a running vllm
  (NVIDIA + Docker) or llama.cpp inference backend. Neither runs in our Colab
  notebook today (no GPU Docker on Colab; llama.cpp build issues there too), so
  there is no real v2 engine wired in yet.
- `MockSuryaOCRService` stands in with a hand-authored fixture shaped exactly like
  Surya v2's `results.json` (see docs/suryaREADME.md "OCR (text recognition)"),
  so C1/C2 can be built and tested against the real output shape today. Swap in a
  real `SuryaV2OCRService` later with zero changes to anything downstream.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from html import unescape
from pathlib import Path


def html_block_to_text(html_content: str) -> str:
    """Surya v2 blocks carry HTML (`<p>`, `<table>`, `<math>`, ...). Flatten to
    plain text for C1, which corrects text, not markup."""
    if not html_content:
        return ""

    text = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
    text = re.sub(r"</(p|tr|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def boxes_from_surya_v2_page(page: dict, page_number: int) -> list[dict]:
    """Adapt one Surya v2 page dict (`blocks` + `image_bbox`) into canonical boxes."""
    boxes = []
    for block in page.get("blocks", []) or []:
        if block.get("skipped") or block.get("error"):
            continue
        text = html_block_to_text(block.get("html", ""))
        if not text:
            continue
        boxes.append({
            "text": text,
            "bbox": block.get("bbox"),
            "confidence": float(block.get("confidence") or 0.0),
            "label": block.get("label", "Text"),
            "page": page_number,
        })
    return boxes


class OCRService(ABC):
    """Pluggable OCR engine contract (FR-08). Implementations return one list of
    canonical boxes per input page/image, in reading order."""

    @abstractmethod
    def run(self, image_paths: list[str]) -> list[list[dict]]:
        raise NotImplementedError


class MockSuryaOCRService(OCRService):
    """Dev/test stand-in for Surya v2 until a real vllm/llama.cpp backend exists.

    Loads a fixture file shaped exactly like Surya's `results.json` (a dict keyed
    by filename, each value a list of per-page dicts with `blocks`/`image_bbox`)
    and ignores the actual `image_paths` — it is not real OCR, only a contract
    stand-in so downstream code can be developed and tested today.
    """

    def __init__(self, fixture_path: str | Path):
        self.fixture_path = Path(fixture_path)

    def run(self, image_paths: list[str]) -> list[list[dict]]:
        data = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        pages = next(iter(data.values()))
        return [
            boxes_from_surya_v2_page(page, page_number=i + 1)
            for i, page in enumerate(pages)
        ]


def get_ocr_service(engine: str | None = None) -> OCRService:
    """Factory for the C1+ pipeline. Only 'mock' is wired today; a real
    'surya_v2' engine is a documented follow-up once an inference backend
    (vllm or llama.cpp) is actually runnable for this project."""
    engine = (engine or "mock").strip().lower()

    if engine == "mock":
        fixture = Path(__file__).resolve().parent / "sample_docs" / "invoice_mock_surya_v2.json"
        return MockSuryaOCRService(fixture)

    raise NotImplementedError(
        f"OCR engine '{engine}' is not wired yet. Only 'mock' is available until "
        "Surya v2 has a running vllm/llama.cpp inference backend (see module docstring)."
    )
