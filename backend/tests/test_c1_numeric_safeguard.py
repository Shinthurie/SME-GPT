"""Iteration 2 — Component 1: numeric safeguard + per-box correction tests.

These tests are pure-Python (no DB, no LLM, no OCR) and run in CI with no
additional secrets.  They verify:
  - extract_digit_sequences()   (digit tokenisation)
  - safe_correct()              (numeric immutability safeguard — research §9.2)
  - correct_box()               (per-box safe dictionary correction)
  - correct_boxes_for_page()    (page-level batch wrapper)
  - compute_cer()               (Character Error Rate metric)
  - compute_nar()               (Numeric Accuracy Rate metric)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_correction import (
    extract_digit_sequences,
    safe_correct,
    correct_box,
    correct_boxes_for_page,
    compute_cer,
    compute_nar,
)


# ── extract_digit_sequences ───────────────────────────────────────────────────

def test_extract_basic():
    assert extract_digit_sequences("Invoice #INV-001, Total: 1500.00") == ["001", "1500", "00"]


def test_extract_empty_string():
    assert extract_digit_sequences("") == []


def test_extract_none():
    assert extract_digit_sequences(None) == []


def test_extract_no_digits():
    assert extract_digit_sequences("No numbers here") == []


def test_extract_only_digits():
    assert extract_digit_sequences("42") == ["42"]


def test_extract_multiple_groups():
    assert extract_digit_sequences("3 items @ Rs. 150 each = Rs. 450") == ["3", "150", "450"]


# ── safe_correct ──────────────────────────────────────────────────────────────

def test_safe_correct_accepts_when_digits_match():
    assert safe_correct("Totl: 1500", "Total: 1500") == "Total: 1500"


def test_safe_correct_rejects_value_change():
    assert safe_correct("Total: 1500", "Total: 1600") == "Total: 1500"


def test_safe_correct_rejects_digit_dropped():
    assert safe_correct("Items: 3  Total: 450", "Items: Total: 450") == "Items: 3  Total: 450"


def test_safe_correct_rejects_digit_added():
    assert safe_correct("Rs. 100", "Rs. 1001") == "Rs. 100"


def test_safe_correct_allows_pure_text_fix():
    result = safe_correct("Invioce Date: 2024-01-15", "Invoice Date: 2024-01-15")
    assert result == "Invoice Date: 2024-01-15"


def test_safe_correct_no_op_when_unchanged():
    assert safe_correct("Invoice", "Invoice") == "Invoice"


def test_safe_correct_handles_none_corrected():
    assert safe_correct("Total: 500", None) == "Total: 500"


def test_safe_correct_handles_none_original():
    assert safe_correct(None, "anything") is None


# ── correct_box ───────────────────────────────────────────────────────────────

def test_correct_box_has_required_keys():
    box = {"text": "Totl: 500.00", "bbox": [0, 0, 100, 20], "confidence": 0.9}
    result = correct_box(box)
    for key in ("text", "bbox", "confidence", "locked_digits", "source"):
        assert key in result, f"missing key: {key}"


def test_correct_box_locks_original_digits():
    box = {"text": "Rs. 1500.00", "bbox": [0, 0, 100, 20], "confidence": 0.95}
    result = correct_box(box)
    assert "1500" in result["locked_digits"]
    assert "00" in result["locked_digits"]


def test_correct_box_never_changes_digits():
    """Whatever dictionary correction does, digit sequences must be preserved."""
    box = {"text": "500 units @ Rs. 25", "bbox": [0, 0, 200, 20], "confidence": 0.85}
    result = correct_box(box)
    assert extract_digit_sequences(result["text"]) == extract_digit_sequences(box["text"])


def test_correct_box_source_original_when_no_change():
    box = {"text": "Invoice", "bbox": [0, 0, 80, 20], "confidence": 0.99}
    result = correct_box(box)
    assert result["source"] in ("original", "dict")


def test_correct_box_passes_through_bbox_and_confidence():
    box = {"text": "Date", "bbox": [10, 20, 90, 40], "confidence": 0.88, "polygon": [[1, 2]]}
    result = correct_box(box)
    assert result["bbox"] == [10, 20, 90, 40]
    assert result["confidence"] == 0.88
    assert result["polygon"] == [[1, 2]]


def test_correct_box_empty_text():
    box = {"text": "", "bbox": [0, 0, 10, 10], "confidence": 0.5}
    result = correct_box(box)
    assert result["locked_digits"] == []
    assert result["text"] == ""


# ── correct_boxes_for_page ────────────────────────────────────────────────────

def test_correct_boxes_for_page_count():
    lines = [
        {"text": "Invoice", "bbox": [0, 0, 100, 20], "confidence": 0.99},
        {"text": "Totl: 250", "bbox": [0, 20, 100, 40], "confidence": 0.87},
        {"text": "Rs. 250.00", "bbox": [0, 40, 100, 60], "confidence": 0.92},
    ]
    result = correct_boxes_for_page(lines)
    assert len(result) == 3


def test_correct_boxes_for_page_empty():
    assert correct_boxes_for_page([]) == []


def test_correct_boxes_for_page_none():
    assert correct_boxes_for_page(None) == []


def test_correct_boxes_for_page_digits_preserved_all():
    lines = [
        {"text": "PO-2024-001", "bbox": [0, 0, 100, 20], "confidence": 0.95},
        {"text": "Total: 9999.99", "bbox": [0, 20, 100, 40], "confidence": 0.91},
    ]
    result = correct_boxes_for_page(lines)
    for orig, corrected in zip(lines, result):
        assert extract_digit_sequences(corrected["text"]) == extract_digit_sequences(orig["text"])


# ── compute_cer ───────────────────────────────────────────────────────────────

def test_cer_identical():
    assert compute_cer("hello", "hello") == 0.0


def test_cer_completely_different():
    cer = compute_cer("abc", "xyz")
    assert 0.0 < cer <= 1.0


def test_cer_one_substitution():
    cer = compute_cer("hello", "helo")
    assert 0.0 < cer < 0.5


def test_cer_empty_original():
    assert compute_cer("", "something") == 0.0


def test_cer_empty_both():
    assert compute_cer("", "") == 0.0


# ── compute_nar ───────────────────────────────────────────────────────────────

def test_nar_all_preserved():
    boxes = [
        {"text": "1500", "locked_digits": ["1500"]},
        {"text": "200", "locked_digits": ["200"]},
    ]
    assert compute_nar(boxes) == 1.0


def test_nar_none_preserved():
    boxes = [
        {"text": "999", "locked_digits": ["1500"]},
    ]
    assert compute_nar(boxes) == 0.0


def test_nar_half_preserved():
    boxes = [
        {"text": "1500", "locked_digits": ["1500"]},
        {"text": "201", "locked_digits": ["200"]},
    ]
    assert compute_nar(boxes) == 0.5


def test_nar_empty_boxes():
    assert compute_nar([]) == 1.0
