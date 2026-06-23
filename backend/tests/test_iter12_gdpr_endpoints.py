"""Iteration 12 — GDPR data export + account deletion (NFR-14).

`GET /user/export` and `DELETE /user/account` are tested directly against
the real FastAPI app via `TestClient` so the auth wiring (`get_current_user_id`)
is exercised exactly as a real request would hit it -- same pattern as the
`/confirm-save` smoke test in test_iter5/test_iter11. The hard-delete SQL
itself is verified hermetically against a fake DB connection (no real
DATABASE_URL needed), mirroring `_log_audit_event`'s test style in
test_iter11_rbac_enforcement.py.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass


@pytest.fixture(scope="module")
def app_module():
    import app as app_mod
    return app_mod


@pytest.fixture()
def client(app_module):
    # raise_server_exceptions=False so the test client returns the response
    # produced by app.py's global Exception handler (Iteration 13) instead
    # of re-raising the original exception for debugging.
    return TestClient(app_module.app, raise_server_exceptions=False)


def _token(app_module, **claims):
    import jwt as pyjwt
    return pyjwt.encode(claims, app_module.JWT_SECRET, algorithm=app_module.JWT_ALGORITHM)


def _bearer(app_module, **claims):
    return f"Bearer {_token(app_module, **claims)}"


# ---------------------------------------------------------------------------
# GET /user/export
# ---------------------------------------------------------------------------

def test_export_requires_auth(client):
    resp = client.get("/user/export")
    assert resp.status_code == 401


def test_export_returns_documents_and_query_history(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "load_all_records", lambda user_id: [{"document_id": "INV1"}])
    monkeypatch.setattr(app_module, "load_query_history_for_user", lambda user_id: [{"id": "q1"}])

    resp = client.get("/user/export", headers={"Authorization": _bearer(app_module, userId="user-1")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["user_id"] == "user-1"
    assert body["documents"] == [{"document_id": "INV1"}]
    assert body["query_history"] == [{"id": "q1"}]
    assert "exported_at" in body


# ---------------------------------------------------------------------------
# DELETE /user/account
# ---------------------------------------------------------------------------

def test_delete_account_requires_auth(client):
    resp = client.delete("/user/account")
    assert resp.status_code == 401


class _FakeCursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params):
        self.calls.append((query, params))


class _FakeConn:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _FakeCursor(self.calls)

    def commit(self):
        pass


def test_delete_account_purges_every_tenant_scoped_table(client, app_module, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "get_db_connection", lambda: _FakeConn(calls))

    resp = client.delete("/user/account", headers={"Authorization": _bearer(app_module, userId="user-1")})

    assert resp.status_code == 200
    assert resp.json()["success"] is True

    tables_hit = {query for query, _ in calls}
    assert any('"DocLink"' in q for q in tables_hit)
    assert any('"ChunkEmbedding"' in q for q in tables_hit)
    assert any('"Entity"' in q for q in tables_hit)
    assert any('"FinancialDocument"' in q for q in tables_hit)
    assert any("query_history" in q for q in tables_hit)

    # Every DELETE is scoped to the caller's id, never an unscoped wipe.
    for _, params in calls:
        assert params == ("user-1",)


def test_delete_account_swallows_nothing_silently_on_db_error(client, app_module, monkeypatch):
    """Unlike audit logging, a failed account-data wipe must NOT look like
    success to the caller -- surface a 500 rather than swallowing the error."""
    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(app_module, "get_db_connection", _boom)

    resp = client.delete("/user/account", headers={"Authorization": _bearer(app_module, userId="user-1")})

    assert resp.status_code == 500
    assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# Live DB round trip (skipped without DATABASE_URL)
# ---------------------------------------------------------------------------

pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping GDPR delete integration test",
)


@pytestmark_db
def test_delete_account_removes_real_financial_document(app_module):
    import uuid

    import db

    test_user_id = f"test_{uuid.uuid4().hex}"
    doc_id = f"fd_{uuid.uuid4().hex}"
    with db.get_conn() as conn:
        conn.cursor().execute(
            'INSERT INTO "User" (id, email, password, "updatedAt") VALUES (%s, %s, %s, NOW())',
            (test_user_id, f"{test_user_id}@example.test", "unused"),
        )
        conn.cursor().execute(
            'INSERT INTO "FinancialDocument" (id, "tenantId", "documentId", "updatedAt") '
            'VALUES (%s, %s, %s, NOW())',
            (doc_id, test_user_id, "INV-TEST-1"),
        )

    try:
        app_module.delete_user_account(authorization=_bearer(app_module, userId=test_user_id))

        with db.get_conn() as conn:
            cur = conn.cursor()
            cur.execute('SELECT 1 FROM "FinancialDocument" WHERE "tenantId" = %s', (test_user_id,))
            assert cur.fetchone() is None
    finally:
        with db.get_conn() as conn:
            conn.cursor().execute('DELETE FROM "FinancialDocument" WHERE "tenantId" = %s', (test_user_id,))
            conn.cursor().execute('DELETE FROM "User" WHERE id = %s', (test_user_id,))
