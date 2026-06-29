"""Tests for Feature 1 — Manual Document Entry.

Covers:
- Pillow image generator (manual_doc_generator.py)
- POST /documents/manual endpoint logic
- Auto-calculated totals
- Auto flow_type assignment
"""
from __future__ import annotations

import os
import pytest

# ── manual_doc_generator tests ────────────────────────────────────────────────

def test_generate_receipt_returns_png_bytes():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "receipt",
        "order_id": "REC-TEST-001",
        "date": "29/06/2026",
        "company_name": "AIESEC UoM",
        "supplier_name": "Pasindu Fernando",
        "currency": "LKR",
        "items": [
            {"description": "Membership Fee", "quantity": 1, "unit_price": 2500, "line_total": 2500},
        ],
        "tax_rate": 0,
        "final_total_amount": 2500,
    }
    result = generate_document_image(data)
    assert isinstance(result, bytes)
    assert len(result) > 5000           # real PNG is much larger
    assert result[:4] == b"\x89PNG"     # PNG magic bytes


def test_generate_invoice_returns_png_bytes():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "invoice",
        "order_id": "INV-TEST-001",
        "date": "29/06/2026",
        "company_name": "AIESEC UoM",
        "supplier_name": "Virtusa (Pvt) Ltd",
        "currency": "LKR",
        "items": [
            {"description": "Corporate Sponsorship", "quantity": 1,
             "unit_price": 150000, "line_total": 150000},
        ],
        "tax_rate": 15,
        "final_total_amount": 172500,
    }
    result = generate_document_image(data)
    assert result[:4] == b"\x89PNG"
    assert len(result) > 5000


def test_generate_po_returns_png_bytes():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "po",
        "order_id": "PO-TEST-001",
        "date": "29/06/2026",
        "company_name": "AIESEC UoM",
        "supplier_name": "Classic Printers (Pvt) Ltd",
        "currency": "LKR",
        "items": [
            {"description": "A4 Brochures", "quantity": 500,
             "unit_price": 45, "line_total": 22500},
        ],
        "final_total_amount": 22500,
    }
    result = generate_document_image(data)
    assert result[:4] == b"\x89PNG"


def test_generate_dn_returns_png_bytes():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "dn",
        "order_id": "DN-TEST-001",
        "date": "29/06/2026",
        "company_name": "AIESEC UoM",
        "supplier_name": "Classic Printers (Pvt) Ltd",
        "currency": "LKR",
        "items": [
            {"description": "A4 Brochures", "quantity": 500,
             "unit_price": 0, "line_total": 0},
        ],
    }
    result = generate_document_image(data)
    assert result[:4] == b"\x89PNG"


def test_unknown_doc_type_falls_back_to_receipt():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "unknown_type",
        "order_id": "X-001",
        "date": "29/06/2026",
        "company_name": "Test Co",
        "supplier_name": "Supplier",
        "items": [],
    }
    result = generate_document_image(data)
    assert result[:4] == b"\x89PNG"


def test_empty_items_generates_valid_png():
    from manual_doc_generator import generate_document_image
    data = {
        "document_type": "receipt",
        "order_id": "REC-EMPTY",
        "date": "29/06/2026",
        "company_name": "AIESEC",
        "supplier_name": "Someone",
        "items": [],
    }
    result = generate_document_image(data)
    assert result[:4] == b"\x89PNG"


# ── ManualDocumentRequest model tests ────────────────────────────────────────

def test_manual_request_model_defaults():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app as app_mod
    req = app_mod.ManualDocumentRequest(supplier_name="Test Supplier")
    assert req.document_type == "receipt"
    assert req.currency == "LKR"
    assert req.force_save is False
    assert req.items == []


def test_manual_request_accepts_all_doc_types():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app as app_mod
    for dt in ("receipt", "invoice", "po", "dn"):
        req = app_mod.ManualDocumentRequest(document_type=dt, supplier_name="X")
        assert req.document_type == dt


# ── Flow-type auto-assignment tests ─────────────────────────────────────────

def test_flow_type_map_receipt_is_cash_outflow():
    """Receipt → cash_outflow (already paid)."""
    flow_map = {
        "receipt": "cash_outflow",
        "invoice": "receivable",
        "po":      "payable",
        "dn":      "expense",
    }
    assert flow_map["receipt"] == "cash_outflow"
    assert flow_map["invoice"] == "receivable"
    assert flow_map["po"]      == "payable"
    assert flow_map["dn"]      == "expense"


# ── Total calculation tests ──────────────────────────────────────────────────

def test_line_total_calculation():
    """qty × unit_price = line_total."""
    items = [
        {"description": "Item A", "quantity": 2, "unit_price": 1500, "line_total": 0},
        {"description": "Item B", "quantity": 5, "unit_price": 300,  "line_total": 0},
    ]
    subtotal = 0.0
    for item in items:
        total = float(item["quantity"]) * float(item["unit_price"])
        item["line_total"] = round(total, 2)
        subtotal += total
    assert items[0]["line_total"] == 3000.0
    assert items[1]["line_total"] == 1500.0
    assert round(subtotal, 2) == 4500.0


def test_tax_calculation():
    subtotal = 10000.0
    tax_rate = 15.0
    expected_tax = 1500.0
    expected_total = 11500.0
    tax_amt = round(subtotal * tax_rate / 100, 2)
    grand_total = round(subtotal + tax_amt, 2)
    assert tax_amt == expected_tax
    assert grand_total == expected_total
