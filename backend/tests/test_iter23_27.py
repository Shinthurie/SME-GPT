"""Tests for Iteration 23 (overdue payment alerts) and 27 (PO approval field).

All hermetic — overdue logic is a pure module; the PO field test only checks
the Pydantic request model. No DB or network.
"""
from __future__ import annotations

from datetime import date

import overdue_alerts as oa


# ──────────────────────────── IT-23: date parsing ───────────────────────────

def test_parse_loose_date_formats():
    assert oa.parse_loose_date("2026-03-15") == date(2026, 3, 15)
    assert oa.parse_loose_date("15/03/2026") == date(2026, 3, 15)
    assert oa.parse_loose_date("15-03-2026") == date(2026, 3, 15)
    assert oa.parse_loose_date("15.03.2026") == date(2026, 3, 15)


def test_parse_loose_date_rejects_empty_and_garbage():
    assert oa.parse_loose_date(None) is None
    assert oa.parse_loose_date("") is None
    assert oa.parse_loose_date("NULL") is None
    assert oa.parse_loose_date("not a date") is None


# ──────────────────────────── IT-23: overdue logic ──────────────────────────

TODAY = date(2026, 6, 28)


def test_payable_past_due_date_is_overdue():
    rec = {"document_id": "PO1", "document_type": "invoice", "flow_type": "payable",
           "invoice_status": "pending", "paid_status": "not_paid",
           "due_date": "01/06/2026", "date": "01/05/2026",
           "supplier_name": "Acme", "payable_amount": 5000, "currency": "LKR"}
    alert = oa.evaluate_record(rec, TODAY)
    assert alert is not None
    assert alert["kind"] == "payable"
    assert alert["days_overdue"] == 27
    assert alert["counterparty"] == "Acme"
    assert alert["amount"] == 5000.0


def test_settled_payable_is_not_overdue():
    rec = {"document_type": "invoice", "flow_type": "payable",
           "invoice_status": "paid", "paid_status": "paid", "due_date": "01/06/2026"}
    assert oa.evaluate_record(rec, TODAY) is None


def test_receivable_aging_past_threshold_without_due_date():
    rec = {"document_id": "IN9", "document_type": "receipt", "flow_type": "receivable",
           "received_status": "not_received", "date": "01/05/2026"}
    alert = oa.evaluate_record(rec, TODAY)
    assert alert is not None
    assert alert["kind"] == "receivable"
    assert alert["days_overdue"] == 58  # 2026-05-01 -> 2026-06-28


def test_receivable_within_threshold_is_not_overdue():
    rec = {"document_type": "receipt", "flow_type": "receivable",
           "received_status": "not_received", "date": "20/06/2026"}
    assert oa.evaluate_record(rec, TODAY) is None


def test_received_receivable_is_not_overdue():
    rec = {"document_type": "receipt", "flow_type": "receivable",
           "received_status": "received", "date": "01/01/2026"}
    assert oa.evaluate_record(rec, TODAY) is None


def test_po_and_dn_and_cash_are_skipped():
    for flow, dtype in (("payable", "po"), ("expense", "dn"), ("cash_inflow", "receipt")):
        rec = {"document_type": dtype, "flow_type": flow, "date": "01/01/2026"}
        assert oa.evaluate_record(rec, TODAY) is None


def test_no_usable_date_is_not_overdue():
    rec = {"document_type": "invoice", "flow_type": "payable",
           "invoice_status": "pending", "due_date": "NULL", "date": "NULL"}
    assert oa.evaluate_record(rec, TODAY) is None


def test_compute_sorts_most_overdue_first():
    recs = [
        {"document_id": "A", "document_type": "invoice", "flow_type": "payable",
         "invoice_status": "pending", "due_date": "20/06/2026"},   # 8 days
        {"document_id": "B", "document_type": "invoice", "flow_type": "payable",
         "invoice_status": "pending", "due_date": "01/06/2026"},   # 27 days
    ]
    alerts = oa.compute_overdue_alerts(recs, today=TODAY)
    assert [a["document_id"] for a in alerts] == ["B", "A"]


def test_compute_handles_empty():
    assert oa.compute_overdue_alerts([], today=TODAY) == []
    assert oa.compute_overdue_alerts(None, today=TODAY) == []


# ──────────────────────────── IT-27: PO approval field ──────────────────────

def test_update_request_accepts_po_status_and_approved_by():
    from app import UpdateDocumentRequest
    req = UpdateDocumentRequest(po_status="approved", approved_by="Jane Silva")
    data = req.dict(exclude_unset=True)
    assert data == {"po_status": "approved", "approved_by": "Jane Silva"}


def test_update_request_omits_po_status_when_unset():
    from app import UpdateDocumentRequest
    req = UpdateDocumentRequest(company_name="X")
    data = req.dict(exclude_unset=True)
    assert "po_status" not in data
    assert "approved_by" not in data
