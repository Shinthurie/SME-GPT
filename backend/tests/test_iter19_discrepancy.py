"""Tests for Iteration 19: GAP-19A cross-document price discrepancy detection."""
from __future__ import annotations


# ──────────────────────────── GAP-19A: find_price_discrepancies ─────────────

def test_find_price_discrepancies_detects_higher_invoice():
    from data_tools import find_price_discrepancies
    inv_items = [{"description": "Portland Cement 20kg", "unit_price": 2450, "quantity": 10, "line_total": 24500}]
    po_items  = [{"description": "Portland Cement 20kg Bag", "unit_price": 2250, "quantity": 10, "line_total": 22500}]
    result = find_price_discrepancies(inv_items, po_items)
    assert len(result) == 1
    d = result[0]
    assert d["is_discrepancy"] is True
    assert d["direction"] == "higher"
    assert abs(d["diff_pct"] - 8.9) < 0.5   # ~8.88%


def test_find_price_discrepancies_no_discrepancy_when_prices_match():
    from data_tools import find_price_discrepancies
    inv_items = [{"description": "Steel Rod 12mm", "unit_price": 500, "quantity": 5, "line_total": 2500}]
    po_items  = [{"description": "Steel Rod 12mm",  "unit_price": 500, "quantity": 5, "line_total": 2500}]
    result = find_price_discrepancies(inv_items, po_items)
    assert len(result) == 1
    assert result[0]["is_discrepancy"] is False


def test_find_price_discrepancies_skips_unmatched_items():
    from data_tools import find_price_discrepancies
    inv_items = [{"description": "Cement Bag",    "unit_price": 300, "quantity": 1, "line_total": 300}]
    po_items  = [{"description": "Steel Pipe XYZ","unit_price": 900, "quantity": 1, "line_total": 900}]
    result = find_price_discrepancies(inv_items, po_items)
    # Descriptions have no common words → similarity < 0.5 → not matched
    assert result == []


def test_detect_discrepancies_in_evidence_requires_invoice_and_po():
    from data_tools import detect_discrepancies_in_evidence
    evidence_invoice_only = [
        {"document_type": "invoice", "items": [{"description": "Item A", "unit_price": 100, "quantity": 1, "line_total": 100}]}
    ]
    assert detect_discrepancies_in_evidence(evidence_invoice_only) == []


def test_detect_discrepancies_in_evidence_returns_empty_when_no_discrepancy():
    from data_tools import detect_discrepancies_in_evidence
    evidence = [
        {"document_type": "invoice", "items": [{"description": "Sand Bags", "unit_price": 150, "quantity": 5, "line_total": 750}]},
        {"document_type": "po",      "items": [{"description": "Sand Bags", "unit_price": 150, "quantity": 5, "line_total": 750}]},
    ]
    result = detect_discrepancies_in_evidence(evidence)
    assert all(not d["is_discrepancy"] for d in result)


# ──────────────────────────── GAP-19C: bilingual note ───────────────────────

def test_build_discrepancy_bilingual_note_en():
    from pal_answer import build_discrepancy_bilingual_note
    discrepancies = [{"description": "Cement", "invoice_price": 2450, "po_price": 2250,
                      "diff_pct": 8.9, "is_discrepancy": True, "direction": "higher"}]
    note = build_discrepancy_bilingual_note(discrepancies, lang="en")
    assert "Cement" in note
    assert "2,450" in note
    assert "higher" in note.lower()
    assert "LKR" in note


def test_build_discrepancy_bilingual_note_si_contains_sinhala():
    from pal_answer import build_discrepancy_bilingual_note
    discrepancies = [{"description": "Cement", "invoice_price": 2450, "po_price": 2250,
                      "diff_pct": 8.9, "is_discrepancy": True, "direction": "higher"}]
    note = build_discrepancy_bilingual_note(discrepancies, lang="si")
    assert "ඉන්වොයිස්" in note   # Sinhala word for "invoice"
    assert "Cement" in note      # description still in English


def test_build_discrepancy_bilingual_note_empty_when_no_actual_discrepancy():
    from pal_answer import build_discrepancy_bilingual_note
    discrepancies = [{"description": "Item", "invoice_price": 100, "po_price": 100,
                      "diff_pct": 0.0, "is_discrepancy": False, "direction": "higher"}]
    note = build_discrepancy_bilingual_note(discrepancies, lang="en")
    assert note == ""
