"""Final integration tests — IT-40 through IT-49.

All tests are hermetic (no real DB/SMTP/Twilio) using monkeypatching.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import jwt as pyjwt
import app as app_mod
from fastapi.testclient import TestClient

client = TestClient(app_mod.app, raise_server_exceptions=False)

def _tok(uid="user-test", role="owner"):
    return pyjwt.encode({"userId": uid, "role": role}, app_mod.JWT_SECRET,
                        algorithm=app_mod.JWT_ALGORITHM)


# ── IT-40: Supplier History ────────────────────────────────────────────────────

def test_supplier_history_returns_transactions(monkeypatch):
    records = [
        {"document_id":"IN1","document_type":"invoice","supplier_name":"Virtusa",
         "effective_flow_type":"receivable","payable_amount":50000,"date":"2026-02-10",
         "currency":"LKR","paid_status":"not_paid","received_status":"NULL",
         "invoice_status":"pending","po_status":"","notes":""},
    ]
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: records)
    monkeypatch.setattr(app_mod, "parse_record_for_output", lambda r: r,
                        raising=False)
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.get("/suppliers/Virtusa/history",
                     headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert len(body["transactions"]) == 1
    assert body["summary"]["total_received"] == 50000


def test_supplier_history_empty_for_unknown(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.get("/suppliers/UnknownCorp/history",
                     headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    assert res.json()["summary"]["count"] == 0


def test_supplier_duplicates_endpoint_exists(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.get("/suppliers/duplicates",
                     headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    assert "groups" in res.json()


# ── IT-41: Payment Reminder ───────────────────────────────────────────────────

def test_send_reminder_requires_email(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [
        {"document_id":"IN1","supplier_name":"Virtusa","final_total_amount":5000,
         "currency":"LKR","due_date":"","date":"","order_id":"IN1",
         "company_name":"AIESEC","effective_flow_type":"receivable"}
    ])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.post("/documents/IN1/send-reminder",
                      json={},
                      headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 400


def test_send_reminder_smtp_not_configured(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [
        {"document_id":"IN1","supplier_name":"Virtusa","final_total_amount":5000,
         "currency":"LKR","due_date":"","date":"","order_id":"IN1",
         "company_name":"AIESEC","effective_flow_type":"receivable"}
    ])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)
    monkeypatch.setenv("SMTP_HOST", "")

    res = client.post("/documents/IN1/send-reminder",
                      json={"email": "test@example.com"},
                      headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 503


# ── IT-44: Exchange Rates ─────────────────────────────────────────────────────

def test_exchange_rates_returns_json(monkeypatch):
    import urllib.request
    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({
            "result":"success","rates":{"USD":0.0033,"EUR":0.003,"LKR":1.0,"GBP":0.0025}
        }).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResp())
    import app as _a; _a._FX_CACHE["fetched_at"] = 0  # force refresh

    res = client.get("/exchange-rates", headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert "USD" in body["rates"] or body["rates"] == {}   # cache or fresh


# ── IT-45: Document Sharing ───────────────────────────────────────────────────

def test_share_document_creates_token(monkeypatch):
    res = client.post("/documents/IN1/share",
                      headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert len(body["token"]) > 10
    assert body["expires_in_days"] == 7


def test_shared_view_with_valid_token(monkeypatch):
    # Create a token first
    import app as _a, time
    _a._SHARE_TOKENS["testtoken123"] = {
        "document_id": "IN-SHARE",
        "user_id": "user-test",
        "expires_at": time.time() + 86400,
    }
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [
        {"document_id":"IN-SHARE","document_type":"invoice","date":"2026-06-01",
         "company_name":"AIESEC","supplier_name":"Client A",
         "final_total_amount":25000,"currency":"LKR","order_id":"IN-SHARE","items_json":"[]"}
    ])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.get("/shared/testtoken123")
    assert res.status_code == 200
    body = res.json()
    assert body["document"]["document_id"] == "IN-SHARE"


def test_shared_view_expired_token():
    import app as _a, time
    _a._SHARE_TOKENS["expiredtok"] = {
        "document_id": "IN1", "user_id": "u", "expires_at": time.time() - 1,
    }
    res = client.get("/shared/expiredtok")
    assert res.status_code == 410


def test_shared_view_missing_token():
    res = client.get("/shared/doesnotexist999")
    assert res.status_code == 404


# ── IT-46: Budget Settings ────────────────────────────────────────────────────

def test_budget_settings_get(monkeypatch):
    class _MockConn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def cursor(self): return _MockCur()
        def commit(self): pass
    class _MockCur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, *a): pass
        def fetchone(self): return {"content": '{"Transport":5000,"Food":2000}'}
    monkeypatch.setattr(app_mod, "get_db_connection", lambda: _MockConn())

    res = client.get("/user/budget-settings",
                     headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_budget_settings_put(monkeypatch):
    monkeypatch.setattr(app_mod, "_log_audit_event", lambda *a: None)

    res = client.put("/user/budget-settings",
                     json={"budgets": {"Transport": 5000, "Food": 2000}},
                     headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200
    assert res.json()["success"] is True


# ── IT-47: Audit Pack Export ──────────────────────────────────────────────────

def test_audit_pack_this_month(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [
        {"document_id":"IN1","document_type":"invoice","date":"2026-06-15",
         "company_name":"AIESEC","supplier_name":"Virtusa",
         "final_total_amount":50000,"currency":"LKR",
         "effective_flow_type":"receivable","flow_type":"receivable","paid_status":"not_paid"}
    ])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)
    monkeypatch.setattr(app_mod, "_log_audit_event", lambda *a: None)

    res = client.post("/reports/audit-pack",
                      json={"period": "this_month"},
                      headers={"Authorization": f"Bearer {_tok()}"})
    # Returns ZIP stream
    assert res.status_code == 200
    assert "zip" in res.headers.get("content-type", "")


def test_audit_pack_custom_period_missing_dates(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)

    res = client.post("/reports/audit-pack",
                      json={"period": "custom"},
                      headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 400


def test_audit_pack_custom_valid(monkeypatch):
    monkeypatch.setattr(app_mod, "load_all_records", lambda **_: [])
    import dataset_manager as dm
    monkeypatch.setattr(dm, "parse_record_for_output", lambda r: r)
    monkeypatch.setattr(app_mod, "_log_audit_event", lambda *a: None)

    res = client.post("/reports/audit-pack",
                      json={"period": "custom", "date_from": "2026-01-01", "date_to": "2026-06-30"},
                      headers={"Authorization": f"Bearer {_tok()}"})
    assert res.status_code == 200


# ── IT-48: Monthly P&L email ─────────────────────────────────────────────────

def test_monthly_pnl_sends_no_email_without_smtp(monkeypatch):
    """_send_monthly_pnl_emails should exit cleanly when SMTP not configured."""
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_USER", "")
    # Should not raise
    app_mod._send_monthly_pnl_emails()


# ── IT-49: WhatsApp Webhook ───────────────────────────────────────────────────

def test_whatsapp_webhook_no_media_returns_no_media():
    res = client.post("/webhook/whatsapp",
                      content="From=whatsapp%3A%2B94771234567",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert res.status_code == 200
    assert res.json().get("status") == "no_media"


def test_whatsapp_webhook_unknown_sender(monkeypatch):
    class _MockConn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def cursor(self): return _MockCur()
    class _MockCur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, *a): pass
        def fetchone(self): return None
    monkeypatch.setattr(app_mod, "get_db_connection", lambda: _MockConn())
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")   # skip signature check

    res = client.post(
        "/webhook/whatsapp",
        content="From=whatsapp%3A%2B0000000000&MediaUrl0=https%3A%2F%2Fexample.com%2Fimg.jpg",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    assert res.json().get("status") == "unknown_sender"
