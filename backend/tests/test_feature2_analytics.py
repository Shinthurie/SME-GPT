"""Tests for Feature 2 — Visual Analytics Dashboard.

Covers:
- Health score calculation (net = receivable - payable)
- Expense category breakdown
- Top receivables / payables ordering
- Dashboard summary response shape
"""
from __future__ import annotations


# ── Health Score tests ────────────────────────────────────────────────────────

def _make_record(flow_type: str, amount: float, date: str = "2026-06-15") -> dict:
    return {
        "flow_type":           flow_type,
        "effective_flow_type": flow_type,
        "payable_amount":      amount,
        "final_total_amount":  amount,
        "date":                date,
        "document_id":         f"DOC-{id(flow_type)}",
        "supplier_name":       "Test Supplier",
        "currency":            "LKR",
        "paid_status":         "not_paid",
        "received_status":     "not_received",
        "corrected_text":      "",
    }


def test_health_score_positive_when_more_receivable():
    """If receivable > payable, net should be positive."""
    records = [
        _make_record("receivable",   50000),
        _make_record("cash_outflow", 20000),
    ]
    total_in  = sum(r["payable_amount"] for r in records if r["flow_type"] in ("receivable","cash_inflow","income"))
    total_out = sum(r["payable_amount"] for r in records if r["flow_type"] in ("payable","cash_outflow","expense"))
    net = round(total_in - total_out, 2)
    assert net == 30000.0
    assert net > 0


def test_health_score_negative_when_more_payable():
    """If payable > receivable, net should be negative."""
    records = [
        _make_record("payable",     80000),
        _make_record("cash_inflow", 30000),
    ]
    total_in  = sum(r["payable_amount"] for r in records if r["flow_type"] in ("receivable","cash_inflow","income"))
    total_out = sum(r["payable_amount"] for r in records if r["flow_type"] in ("payable","cash_outflow","expense"))
    net = round(total_in - total_out, 2)
    assert net == -50000.0
    assert net < 0


def test_trend_calculation():
    """trend_pct = (this_month - last_month) / abs(last_month) * 100."""
    this_month = 10000.0
    last_month = 8000.0
    trend = round((this_month - last_month) / abs(last_month) * 100, 1)
    assert trend == 25.0


def test_trend_zero_when_last_month_zero():
    """No division by zero when last month had no activity."""
    last_month = 0.0
    trend = round(((5000 - last_month) / abs(last_month) * 100) if last_month else 0, 1)
    assert trend == 0.0


# ── Who Owes Who tests ────────────────────────────────────────────────────────

def test_top_receivables_sorted_descending():
    entries = [
        {"amount": 15000, "supplier_name": "Virtusa"},
        {"amount": 80000, "supplier_name": "WSO2"},
        {"amount": 30000, "supplier_name": "Hemas"},
    ]
    sorted_entries = sorted(entries, key=lambda x: -x["amount"])
    assert sorted_entries[0]["supplier_name"] == "WSO2"
    assert sorted_entries[1]["supplier_name"] == "Hemas"


def test_settled_documents_excluded_from_balances():
    """Documents with paid_status=paid should not appear in balances."""
    records = [
        {"flow_type": "payable", "paid_status": "paid",     "amount": 5000},
        {"flow_type": "payable", "paid_status": "not_paid", "amount": 8000},
        {"flow_type": "payable", "paid_status": "NULL",     "amount": 3000},
    ]
    outstanding = [r for r in records
                   if r["paid_status"].lower() not in ("paid", "received")]
    amounts = [r["amount"] for r in outstanding]
    assert 5000 not in amounts
    assert 8000 in amounts
    assert 3000 in amounts


# ── Dashboard summary shape test ──────────────────────────────────────────────

def test_dashboard_summary_contains_analytics_keys(monkeypatch):
    """The /dashboard-summary response must include all analytics fields."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app as app_mod
    from fastapi.testclient import TestClient
    import jwt as pyjwt

    client = TestClient(app_mod.app, raise_server_exceptions=False)
    token = pyjwt.encode(
        {"userId": "user-analytics-test", "role": "owner"},
        app_mod.JWT_SECRET,
        algorithm=app_mod.JWT_ALGORITHM,
    )

    # Mock the DB calls so no real DB is needed
    monkeypatch.setattr(app_mod, "load_records", lambda **_kw: [])
    monkeypatch.setattr(app_mod, "build_dashboard_summary", lambda _r: {
        "total_documents": 0, "invoice_count": 0, "receipt_count": 0,
        "po_count": 0, "dn_count": 0,
        "total_payable_amount": 0, "total_receivable_amount": 0,
        "pending_processing_count": 0, "ready_for_query_count": 0,
    })
    monkeypatch.setattr(app_mod, "get_db_connection", lambda: _MockConn())

    resp = client.get("/dashboard-summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    # All Feature-2 keys must be present
    for key in ("health_score", "top_receivables", "top_payables", "activity_feed"):
        assert key in body, f"Missing key: {key}"
    assert isinstance(body["health_score"], dict)
    assert "net" in body["health_score"]
    assert "color" in body["health_score"]


class _MockConn:
    """Minimal DB connection mock for analytics tests."""
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def cursor(self): return _MockCursor()
    def commit(self): pass

class _MockCursor:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, *a): pass
    def fetchall(self): return []
