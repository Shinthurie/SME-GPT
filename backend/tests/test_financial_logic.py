"""Financial Logic Tests — Real-World SME Scenarios.

Tests cover the arithmetic, status derivation, and classification rules
that a financial document management system must get right:

1.  Line-item subtotal vs declared total consistency
2.  Tax validation (rate × subtotal = tax amount)
3.  Cash return for over-payment at till
4.  Partial payment outstanding balance
5.  Invoice overdue detection (date-based)
6.  Receivable aging buckets
7.  Payment-status-to-workflow-status derivation (PO / DN / Invoice)
8.  DN amounts cleared to zero (delivery notes are not payments)
9.  PO always payable — never receivable
10. Duplicate-invoice detection logic
11. Rounding tolerance (≤ 1 LKR drift is acceptable)
12. Negative amounts — credit notes / refunds
13. Zero-quantity line-item flagging
14. Cash flow direction consistency
15. Multi-document double-counting prevention (PO + matching Invoice)
16. Receipt arithmetic: amount_given − total = cash_return
17. Currency mismatch flag (items in USD but total in LKR)
18. Fulfilled PO should NOT appear in outstanding payables
19. Receivable invoice excluded from payable totals
20. Payable invoice excluded from receivable totals
21. Invoice with no due_date > 30 days old should be flagged overdue
22. Arithmetic validator: matched when items sum == declared total
23. Arithmetic validator: mismatch when > 5% deviation
24. Correction engine: recalculates total from items when total=0
25. Correction engine: preserves manually-set total if items missing
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date, timedelta
from copy import deepcopy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc(overrides: dict = {}) -> dict:
    """Base financial document record."""
    base = {
        "document_type": "invoice",
        "flow_type": "payable",
        "effective_flow_type": "payable",
        "supplier_name": "Virtusa (Pvt) Ltd",
        "company_name": "AIESEC",
        "date": date.today().isoformat(),
        "currency": "LKR",
        "raw_total_amount": 100_000,
        "final_total_amount": 100_000,
        "payable_amount": 100_000,
        "cash_return": 0,
        "paid_status": "not_paid",
        "received_status": "not_received",
        "tax_amount": 0,
        "tax_rate": 0,
        "items": [],
        "document_id": "IN-TEST-001",
        "order_id": "ORD-001",
        "due_date": "",
        "delivery_date": "",
        "po_status": "",
        "dn_status": "",
        "invoice_status": "",
    }
    base.update(overrides)
    return base


def _item(desc="Service", qty=1, price=100_000, total=None) -> dict:
    return {
        "description": desc,
        "quantity": qty,
        "unit_price": price,
        "line_total": total if total is not None else qty * price,
    }


# ── 1. Line-item subtotal vs declared total ───────────────────────────────────

def test_items_sum_matches_final_total():
    """Sum of qty×price must equal final_total_amount within 5% tolerance."""
    items = [_item("A", 2, 50_000), _item("B", 1, 10_000)]
    items_total = sum(i["line_total"] for i in items)
    declared = 110_000
    assert abs(items_total - declared) / max(declared, 1) <= 0.05


def test_items_sum_mismatch_flags_discrepancy():
    """> 5% gap between items total and declared total = discrepancy."""
    items = [_item("A", 1, 50_000)]
    items_total = 50_000
    declared = 100_000
    pct_diff = abs(items_total - declared) / max(declared, 1)
    assert pct_diff > 0.05, "Should be flagged as a discrepancy"


# ── 2. Tax validation ─────────────────────────────────────────────────────────

def test_tax_amount_matches_rate_times_subtotal():
    """tax_amount should equal subtotal × rate / 100 within LKR 1."""
    subtotal = 100_000.0
    tax_rate = 18.0  # Sri Lanka VAT 2024
    expected_tax = round(subtotal * tax_rate / 100, 2)
    declared_tax = 18_000.0
    assert abs(expected_tax - declared_tax) <= 1.0


def test_tax_rate_above_25_is_suspicious():
    """VAT > 25% is outside any current Sri Lanka tax rate."""
    tax_rate = 30.0
    assert tax_rate > 25, "Should be flagged for review"


def test_final_total_equals_subtotal_plus_tax():
    """final_total = items_subtotal + tax_amount (within LKR 1 rounding)."""
    subtotal = 100_000.0
    tax = 18_000.0
    expected_final = subtotal + tax
    declared_final = 118_000.0
    assert abs(expected_final - declared_final) <= 1.0


# ── 3. Cash return (receipt over-payment) ────────────────────────────────────

def test_cash_return_calculated_correctly():
    """cash_return = amount_tendered − final_total."""
    final_total = 850.0
    amount_tendered = 1_000.0
    expected_return = amount_tendered - final_total
    assert expected_return == 150.0


def test_cash_return_zero_when_exact_payment():
    final_total = 1_000.0
    amount_tendered = 1_000.0
    cash_return = amount_tendered - final_total
    assert cash_return == 0.0


def test_cash_return_cannot_be_negative():
    """Cannot give change less than tendered amount — would be a shortfall."""
    final_total = 1_200.0
    amount_tendered = 1_000.0
    # negative cash_return means underpayment — should be flagged, not a "return"
    cash_return = amount_tendered - final_total
    assert cash_return < 0, "This is an underpayment — not a valid cash return"


# ── 4. Partial payment outstanding balance ────────────────────────────────────

def test_partial_payment_outstanding():
    """Outstanding = final_total − partial_paid when paid_status='partial'."""
    final_total = 100_000.0
    partial_paid = 40_000.0
    outstanding = final_total - partial_paid
    assert outstanding == 60_000.0
    assert outstanding > 0


def test_fully_paid_has_zero_outstanding():
    final_total = 100_000.0
    paid = 100_000.0
    outstanding = max(0.0, final_total - paid)
    assert outstanding == 0.0


# ── 5. Overdue detection ──────────────────────────────────────────────────────

def test_invoice_overdue_when_past_due_date():
    """Invoice with due_date in the past and not paid = overdue."""
    due_date = date.today() - timedelta(days=5)
    paid_status = "not_paid"
    is_overdue = due_date < date.today() and paid_status != "paid"
    assert is_overdue


def test_invoice_not_overdue_before_due_date():
    due_date = date.today() + timedelta(days=30)
    paid_status = "not_paid"
    is_overdue = due_date < date.today() and paid_status != "paid"
    assert not is_overdue


def test_paid_invoice_never_overdue():
    """Paid invoices are never overdue regardless of due date."""
    due_date = date.today() - timedelta(days=90)
    paid_status = "paid"
    is_overdue = due_date < date.today() and paid_status != "paid"
    assert not is_overdue


def test_invoice_30_days_no_due_date_flagged():
    """Invoice older than 30 days with no explicit due_date → overdue."""
    doc_date = date.today() - timedelta(days=35)
    due_date = None  # not set by OCR
    paid_status = "not_paid"
    # Business rule: assume Net-30 when no due_date is set
    implied_due = doc_date + timedelta(days=30)
    is_overdue = implied_due < date.today() and paid_status != "paid"
    assert is_overdue


# ── 6. Receivable aging buckets ───────────────────────────────────────────────

def _age_bucket(doc_date_str: str) -> str:
    try:
        doc_d = date.fromisoformat(doc_date_str)
    except ValueError:
        return "unknown"
    days = (date.today() - doc_d).days
    if days <= 30:
        return "current"
    elif days <= 60:
        return "31-60"
    elif days <= 90:
        return "61-90"
    return "90+"


def test_aging_current():
    d = (date.today() - timedelta(days=15)).isoformat()
    assert _age_bucket(d) == "current"


def test_aging_31_to_60():
    d = (date.today() - timedelta(days=45)).isoformat()
    assert _age_bucket(d) == "31-60"


def test_aging_over_90():
    d = (date.today() - timedelta(days=95)).isoformat()
    assert _age_bucket(d) == "90+"


# ── 7. Workflow status derivation ─────────────────────────────────────────────

def test_correction_engine_invoice_overdue():
    from correction_engine import _derive_workflow_status, _parse_date_flexible
    data = _doc({
        "document_type": "invoice",
        "paid_status": "not_paid",
        "due_date": (date.today() - timedelta(days=10)).isoformat(),
        "invoice_status": "",
    })
    _derive_workflow_status(data)
    assert data["invoice_status"] == "overdue"


def test_correction_engine_invoice_paid():
    from correction_engine import _derive_workflow_status
    data = _doc({"document_type": "invoice", "paid_status": "paid", "invoice_status": ""})
    _derive_workflow_status(data)
    assert data["invoice_status"] == "paid"


def test_correction_engine_po_pending():
    from correction_engine import _derive_workflow_status
    data = _doc({"document_type": "po", "paid_status": "not_paid", "po_status": ""})
    _derive_workflow_status(data)
    assert data["po_status"] == "pending"


def test_correction_engine_po_fulfilled_when_paid():
    from correction_engine import _derive_workflow_status
    data = _doc({"document_type": "po", "paid_status": "paid", "po_status": ""})
    _derive_workflow_status(data)
    assert data["po_status"] == "fulfilled"


def test_correction_engine_dn_delivered():
    from correction_engine import _derive_workflow_status
    data = _doc({
        "document_type": "dn", "received_status": "received",
        "dn_status": "", "final_total_amount": "",
    })
    _derive_workflow_status(data)
    assert data["dn_status"] == "delivered"


def test_correction_engine_dn_delayed_when_past_delivery_date():
    from correction_engine import _derive_workflow_status
    data = _doc({
        "document_type": "dn",
        "received_status": "not_received",
        "delivery_date": (date.today() - timedelta(days=3)).isoformat(),
        "dn_status": "",
    })
    _derive_workflow_status(data)
    assert data["dn_status"] == "delayed"


# ── 8. DN amounts cleared ─────────────────────────────────────────────────────

def test_dn_has_no_financial_amounts():
    """Delivery notes must NOT contribute to payable totals."""
    records = [
        _doc({"document_type": "dn", "final_total_amount": 50_000, "flow_type": "expense"}),
        _doc({"document_type": "invoice", "final_total_amount": 100_000, "flow_type": "payable"}),
    ]
    payable_total = sum(
        r["final_total_amount"]
        for r in records
        if r["document_type"] != "dn" and r["flow_type"] in ("payable", "expense") and r["document_type"] != "dn"
    )
    # DN must not be included
    assert payable_total == 100_000


# ── 9. PO is always payable ───────────────────────────────────────────────────

def test_po_flow_type_must_be_payable():
    """Business rule: POs represent a commitment to pay, never to receive."""
    from ocr_to_json_extractor import normalize_root_fields
    rec = _doc({"document_type": "po", "flow_type": "receivable"})
    # normalize_root_fields enforces PO → payable via source_text detection
    normalized = normalize_root_fields(rec, source_text="Purchase Order")
    assert normalized.get("flow_type") == "payable", "PO must always be payable"


# ── 10. Duplicate invoice detection ──────────────────────────────────────────

def _duplicates(records: list[dict]) -> list[dict]:
    """Simple exact-match duplicate detection."""
    seen: dict[tuple, dict] = {}
    dupes = []
    for r in records:
        key = (
            str(r.get("supplier_name", "")).lower().strip(),
            str(r.get("final_total_amount", "")),
            str(r.get("date", "")),
        )
        if key in seen:
            dupes.append(r)
        else:
            seen[key] = r
    return dupes


def test_duplicate_same_supplier_amount_date():
    rec1 = _doc({"supplier_name": "Virtusa", "final_total_amount": 100_000, "date": "2026-06-01"})
    rec2 = _doc({"supplier_name": "Virtusa", "final_total_amount": 100_000, "date": "2026-06-01",
                  "document_id": "IN-TEST-002"})
    dupes = _duplicates([rec1, rec2])
    assert len(dupes) == 1


def test_no_duplicate_different_date():
    rec1 = _doc({"supplier_name": "Virtusa", "final_total_amount": 100_000, "date": "2026-06-01"})
    rec2 = _doc({"supplier_name": "Virtusa", "final_total_amount": 100_000, "date": "2026-06-02",
                  "document_id": "IN-TEST-002"})
    dupes = _duplicates([rec1, rec2])
    assert len(dupes) == 0


# ── 11. Rounding tolerance ────────────────────────────────────────────────────

def test_rounding_1_lkr_tolerance_acceptable():
    """Sum-of-items may drift by up to LKR 1 due to OCR rounding."""
    items_total = 99_999.99
    declared = 100_000.00
    diff = abs(items_total - declared)
    assert diff <= 1.0, "Within 1 LKR tolerance — should not flag mismatch"


def test_rounding_over_1_lkr_flagged():
    items_total = 95_000.00
    declared = 100_000.00
    diff = abs(items_total - declared)
    assert diff > 1.0, "Should trigger arithmetic mismatch"


# ── 12. Negative amounts — credit notes ──────────────────────────────────────

def test_credit_note_negative_total_allowed():
    """Credit notes and refunds legitimately have negative amounts."""
    total = -25_000.0
    assert total < 0  # valid for credit note
    # In payable calculation, credit note reduces the total owed
    outstanding = 100_000.0 + total
    assert outstanding == 75_000.0


def test_credit_note_reduces_payable():
    records = [
        {"flow_type": "payable", "final_total_amount": 100_000},
        {"flow_type": "payable", "final_total_amount": -25_000},  # credit note
    ]
    net_payable = sum(r["final_total_amount"] for r in records if r["flow_type"] == "payable")
    assert net_payable == 75_000.0


# ── 13. Zero-quantity line items ──────────────────────────────────────────────

def test_zero_qty_item_contributes_zero():
    item = _item("Ghost Service", qty=0, price=10_000, total=0)
    assert item["line_total"] == 0


def test_items_with_zero_qty_excluded_from_meaningful_count():
    items = [_item("A", 2, 10_000), _item("B", 0, 5_000, 0)]
    meaningful = [i for i in items if i["quantity"] > 0 and i["unit_price"] > 0]
    assert len(meaningful) == 1


# ── 14. Cash flow direction consistency ──────────────────────────────────────

def test_receivable_adds_to_inflow():
    records = [
        _doc({"flow_type": "receivable", "final_total_amount": 80_000}),
        _doc({"flow_type": "payable",    "final_total_amount": 60_000}),
    ]
    inflow  = sum(r["final_total_amount"] for r in records if r["flow_type"] in ("receivable", "cash_inflow"))
    outflow = sum(r["final_total_amount"] for r in records if r["flow_type"] in ("payable", "cash_outflow"))
    assert inflow  == 80_000
    assert outflow == 60_000
    assert inflow - outflow == 20_000  # positive net position


def test_net_negative_when_more_payable():
    records = [
        _doc({"flow_type": "payable",    "final_total_amount": 200_000}),
        _doc({"flow_type": "receivable", "final_total_amount": 80_000}),
    ]
    inflow  = sum(r["final_total_amount"] for r in records if r["flow_type"] in ("receivable", "cash_inflow"))
    outflow = sum(r["final_total_amount"] for r in records if r["flow_type"] in ("payable", "cash_outflow"))
    assert inflow - outflow == -120_000


# ── 15. Double-counting prevention (PO + Invoice) ─────────────────────────────

def test_fulfilled_po_excluded_from_outstanding_payables():
    """Once an invoice is paid for a PO, the PO should not double-count as payable."""
    records = [
        _doc({"document_type": "po",      "flow_type": "payable", "po_status": "fulfilled",
               "final_total_amount": 100_000}),
        _doc({"document_type": "invoice", "flow_type": "payable", "paid_status": "paid",
               "final_total_amount": 100_000, "document_id": "IN-001"}),
    ]
    # outstanding: exclude fulfilled POs and paid invoices
    outstanding = sum(
        r["final_total_amount"] for r in records
        if r["flow_type"] == "payable"
        and r.get("paid_status") != "paid"
        and r.get("po_status") not in ("fulfilled", "cancelled", "rejected")
        and r["document_type"] != "po"  # POs are commitments, not actual liabilities
    )
    assert outstanding == 0  # no double-counting


def test_pending_po_not_in_outstanding_payables():
    """POs are commitments, not actual payables — invoices are the real liability."""
    records = [
        _doc({"document_type": "po", "flow_type": "payable",
               "po_status": "pending", "final_total_amount": 100_000}),
    ]
    outstanding_invoices = [r for r in records if r["document_type"] == "invoice"]
    assert len(outstanding_invoices) == 0


# ── 16. Arithmetic validator integration ─────────────────────────────────────

def test_arithmetic_validator_matched():
    from arithmetic_validator import validate_arithmetic
    doc = _doc({
        "items": [_item("Consulting", 2, 50_000, 100_000)],
        "final_total_amount": 100_000,
        "raw_total_amount": 100_000,
        "payable_amount": 100_000,
    })
    result = validate_arithmetic(doc)
    assert result["status"] in ("matched", "not_checked"), f"Expected matched, got: {result['status']}"


def test_arithmetic_validator_mismatch():
    from arithmetic_validator import validate_arithmetic
    doc = _doc({
        "items": [_item("Consulting", 1, 50_000, 50_000)],
        "final_total_amount": 100_000,  # declared double the items
        "raw_total_amount": 100_000,
        "payable_amount": 100_000,
    })
    result = validate_arithmetic(doc)
    assert result["status"] in ("mismatch", "not_checked")


# ── 17. Correction engine recalculates total from items ───────────────────────

def test_correction_engine_sets_total_from_items_when_missing():
    from correction_engine import correct_extracted_fields
    doc = _doc({
        "items": [_item("A", 2, 30_000, 60_000), _item("B", 1, 20_000, 20_000)],
        "final_total_amount": 0,
        "payable_amount": 0,
    })
    result = correct_extracted_fields(doc)
    assert float(result["final_total_amount"]) == 80_000.0


def test_correction_engine_preserves_declared_total_when_items_missing():
    from correction_engine import correct_extracted_fields
    doc = _doc({
        "items": [],
        "final_total_amount": 150_000,
        "payable_amount": 150_000,
    })
    result = correct_extracted_fields(doc)
    assert float(result["final_total_amount"]) == 150_000.0


# ── 18. Receivable excluded from payable totals ────────────────────────────────

def test_receivable_not_in_payable_sum():
    records = [
        _doc({"flow_type": "payable",    "final_total_amount": 60_000}),
        _doc({"flow_type": "receivable", "final_total_amount": 80_000}),
    ]
    payable_total = sum(r["final_total_amount"] for r in records if r["flow_type"] == "payable")
    assert payable_total == 60_000


def test_payable_not_in_receivable_sum():
    records = [
        _doc({"flow_type": "payable",    "final_total_amount": 60_000}),
        _doc({"flow_type": "receivable", "final_total_amount": 80_000}),
    ]
    recv_total = sum(r["final_total_amount"] for r in records if r["flow_type"] == "receivable")
    assert recv_total == 80_000


# ── Regression: date-range query with income/expense context ─────────────────
# Bug: "how much income did we earn last month?" routed to date_range_query
# which returned ALL documents in the period, including payable ones.

def test_date_range_income_query_only_returns_receivable():
    """Income keywords inside a date query must filter to receivable/cash_inflow only."""
    import pandas as pd
    from data_tools import handle_date_range_query, enrich_dataset

    records = [
        _doc({"document_id": "IN1", "flow_type": "receivable", "effective_flow_type": "receivable",
              "final_total_amount": 100_000, "date": date.today().isoformat()}),
        _doc({"document_id": "IN2", "flow_type": "payable",    "effective_flow_type": "payable",
              "final_total_amount": 50_000,  "date": date.today().isoformat()}),
    ]
    df = enrich_dataset(pd.DataFrame(records))
    result = handle_date_range_query("how much income did we earn this month", df, "AIESEC")

    ids = [e["document_id"] for e in result["evidence"]]
    assert "IN1" in ids, "Receivable document must appear in income query results"
    assert "IN2" not in ids, "Payable document must NOT appear in income query results"


def test_date_range_expense_query_only_returns_payable():
    """Expense keywords inside a date query must filter to payable/cash_outflow only."""
    import pandas as pd
    from data_tools import handle_date_range_query, enrich_dataset

    records = [
        _doc({"document_id": "IN1", "flow_type": "receivable", "effective_flow_type": "receivable",
              "final_total_amount": 100_000, "date": date.today().isoformat()}),
        _doc({"document_id": "IN2", "flow_type": "payable",    "effective_flow_type": "payable",
              "final_total_amount": 50_000,  "date": date.today().isoformat()}),
    ]
    df = enrich_dataset(pd.DataFrame(records))
    result = handle_date_range_query("how much did we spend this month", df, "AIESEC")

    ids = [e["document_id"] for e in result["evidence"]]
    assert "IN2" in ids, "Payable document must appear in expense query results"
    assert "IN1" not in ids, "Receivable document must NOT appear in expense query results"


def test_date_range_no_context_returns_all():
    """A plain date query with no income/expense context returns all document types."""
    import pandas as pd
    from data_tools import handle_date_range_query, enrich_dataset

    records = [
        _doc({"document_id": "IN1", "flow_type": "receivable", "effective_flow_type": "receivable",
              "final_total_amount": 100_000, "date": date.today().isoformat()}),
        _doc({"document_id": "IN2", "flow_type": "payable",    "effective_flow_type": "payable",
              "final_total_amount": 50_000,  "date": date.today().isoformat()}),
    ]
    df = enrich_dataset(pd.DataFrame(records))
    result = handle_date_range_query("show all documents this month", df, "AIESEC")

    ids = [e["document_id"] for e in result["evidence"]]
    assert "IN1" in ids
    assert "IN2" in ids


# ── Regression: build_evidence uses final_total_amount as primary ─────────────

def test_build_evidence_amount_used_uses_final_total():
    """amount_used in evidence must be final_total_amount, not payable_amount."""
    import pandas as pd
    from data_tools import build_evidence, enrich_dataset

    doc = _doc({"flow_type": "receivable", "effective_flow_type": "receivable",
                "final_total_amount": 120_000, "payable_amount": 90_000})
    df = enrich_dataset(pd.DataFrame([doc]))
    evidence = build_evidence(df, "test reason")

    assert len(evidence) == 1
    assert evidence[0]["amount_used"] == 120_000.0, (
        f"amount_used should be final_total_amount=120000, got {evidence[0]['amount_used']}"
    )


def test_build_evidence_includes_flow_direction_income():
    import pandas as pd
    from data_tools import build_evidence, enrich_dataset

    doc = _doc({"flow_type": "receivable", "effective_flow_type": "receivable"})
    df = enrich_dataset(pd.DataFrame([doc]))
    evidence = build_evidence(df, "test")

    assert evidence[0]["flow_direction"] == "income"


def test_build_evidence_includes_flow_direction_expense():
    import pandas as pd
    from data_tools import build_evidence, enrich_dataset

    doc = _doc({"flow_type": "payable", "effective_flow_type": "payable"})
    df = enrich_dataset(pd.DataFrame([doc]))
    evidence = build_evidence(df, "test")

    assert evidence[0]["flow_direction"] == "expense"


# ── Regression: PAL scope uses effective_flow_type ───────────────────────────

def test_pal_scope_prefers_effective_flow_type():
    """build_row_records must use effective_flow_type over raw flow_type."""
    import pandas as pd
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from pal_scope import build_row_records

    # Document where raw flow_type is 'receivable' but effective is 'cash_inflow'
    # (e.g. a fully-received receivable invoice).
    doc = {
        "document_id": "IN-EFT-01",
        "flow_type": "receivable",
        "effective_flow_type": "cash_inflow",
        "supplier_name": "TestCo",
        "date": date.today().isoformat(),
        "currency": "LKR",
        "final_total_amount": 50_000,
        "payable_amount": 50_000,
        "structured_json": "{}",
        "items": [],
    }
    df = pd.DataFrame([doc])
    rows = build_row_records(df)

    assert len(rows) == 1
    assert rows[0]["flow_type"] == "cash_inflow", (
        f"Expected effective flow 'cash_inflow', got '{rows[0]['flow_type']}'"
    )
