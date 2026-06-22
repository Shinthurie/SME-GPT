"""Iteration 2 — Component 1 (box-level OCR correction) tests.

Covers: the numeric safeguard (safe_correct), the Surya v2 HTML->text adapter,
the mock OCRService fixture, and the end-to-end correct_pages() pipeline. The
pipeline test monkeypatches the DeepSeek call so it's hermetic (no network/API
key needed) and deterministically exercises the raw_ocr fallback path.
"""
import json
from pathlib import Path

import ocr_correction
from ocr_correction import (
    build_quality_report,
    correct_pages,
    extract_digits,
    safe_correct,
    write_final_safe_boxes,
)
from ocr_service import (
    MockSuryaOCRService,
    get_ocr_service,
    html_block_to_text,
)

FIXTURE = Path(__file__).resolve().parent.parent / "sample_docs" / "invoice_mock_surya_v2.json"


def test_extract_digits():
    assert extract_digits("Rs 1,300.00") == "130000"
    assert extract_digits("no numbers here") == ""
    assert extract_digits(None) == ""


def test_safe_correct_accepts_identical_digits():
    text, source = safe_correct("Rs 1,300", "Rs. 1,300")
    assert source == "ai_corrected"
    assert text == "Rs. 1,300"


def test_safe_correct_accepts_pure_text_with_no_digits():
    text, source = safe_correct("Toatl", "Total")
    assert source == "ai_corrected"
    assert text == "Total"


def test_safe_correct_rejects_changed_digit_count():
    # "S" instead of "5" -> raw has one fewer real digit than the LLM's "fix".
    text, source = safe_correct("07726920S7", "0772692057")
    assert source == "raw_ocr"
    assert text == "07726920S7"


def test_safe_correct_rejects_changed_digit_sequence():
    text, source = safe_correct("Total 600", "Total 900")
    assert source == "raw_ocr"
    assert text == "Total 600"


def test_safe_correct_rejects_decimal_structure_change():
    # Same digits (5,0,0,0,0) but the decimal point moved -> different value.
    text, source = safe_correct("500.00", "5000.0")
    assert source == "raw_ocr"
    assert text == "500.00"


def test_safe_correct_ignores_thousands_separator_changes():
    # Adding/removing a comma doesn't change the digit sequence or decimal
    # structure, so this is safe to accept.
    text, source = safe_correct("1300", "1,300")
    assert source == "ai_corrected"
    assert text == "1,300"


def test_html_block_to_text_strips_tags_and_entities():
    assert html_block_to_text("<p>Cash return</p>") == "Cash return"
    assert html_block_to_text("<p>Rs&nbsp;200</p>").startswith("Rs")
    assert html_block_to_text("") == ""
    assert html_block_to_text(None) == ""


def test_html_block_to_text_flattens_table_rows():
    html = "<table><tr><td>1</td><td>Item</td><td>600</td></tr></table>"
    text = html_block_to_text(html)
    assert "1" in text and "Item" in text and "600" in text


def test_mock_fixture_loads_expected_box_count():
    assert FIXTURE.exists()
    service = MockSuryaOCRService(FIXTURE)
    pages = service.run(["invoice.png"])

    assert len(pages) == 1
    # The fixture has 11 blocks, 1 of which is a skipped Picture -> 10 text boxes.
    assert len(pages[0]) == 10
    assert all(box["text"] for box in pages[0])
    assert all("bbox" in box and "confidence" in box and "page" in box for box in pages[0])


def test_get_ocr_service_default_is_mock():
    service = get_ocr_service()
    pages = service.run(["invoice.png"])
    assert pages and pages[0]


def test_get_ocr_service_unknown_engine_raises():
    import pytest
    with pytest.raises(NotImplementedError):
        get_ocr_service("surya_v2")


def test_correct_pages_falls_back_to_raw_without_deepseek(monkeypatch):
    def _boom(_prompt):
        raise RuntimeError("no network in test")

    monkeypatch.setattr(ocr_correction, "call_ollama", _boom)

    service = MockSuryaOCRService(FIXTURE)
    pages = service.run(["invoice.png"])
    corrected = correct_pages(pages)

    assert len(corrected) == len(pages)
    for page_index, page in enumerate(corrected):
        original_boxes = pages[page_index]
        assert len(page["boxes"]) == len(original_boxes)
        for box, original in zip(page["boxes"], original_boxes):
            assert box["source"] == "raw_ocr"
            assert box["text"] == original["text"]
            assert box["bbox"] == original["bbox"]


def test_correct_pages_never_alters_digits_even_when_deepseek_corrupts_them(monkeypatch):
    # Simulate a misbehaving LLM that "fixes" a number — the safeguard must
    # still keep the raw digits no matter what DeepSeek returns.
    def _corrupt(_prompt):
        return "Total 999999"

    monkeypatch.setattr(ocr_correction, "call_ollama", _corrupt)

    box = {"text": "Total 600", "bbox": [0, 0, 1, 1], "confidence": 0.9, "label": "Text", "page": 1}
    result = ocr_correction.correct_box(box)

    assert result["source"] == "raw_ocr"
    assert result["text"] == "Total 600"
    assert result["locked_digits"] is True


def test_write_final_safe_boxes_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_correction, "call_ollama", lambda _p: (_ for _ in ()).throw(RuntimeError("offline")))

    service = MockSuryaOCRService(FIXTURE)
    pages = service.run(["invoice.png"])
    corrected = correct_pages(pages)
    out = write_final_safe_boxes(corrected, tmp_path / "final_safe_boxes.json")

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    for page in loaded:
        assert "page" in page and "boxes" in page
        for box in page["boxes"]:
            assert {"text", "bbox", "confidence", "locked_digits", "source"}.issubset(box.keys())


def test_quality_report_numeric_accuracy_always_one(monkeypatch):
    monkeypatch.setattr(ocr_correction, "call_ollama", lambda _p: (_ for _ in ()).throw(RuntimeError("offline")))

    service = MockSuryaOCRService(FIXTURE)
    pages = service.run(["invoice.png"])
    corrected = correct_pages(pages)
    report = build_quality_report(corrected)

    assert report["numeric_accuracy_rate"] == 1.0
    assert report["total_boxes"] == report["ai_corrected_boxes"] + report["raw_ocr_boxes"]
    assert report["numeric_boxes"] >= 1
