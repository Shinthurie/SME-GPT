"""Iteration 11 — RBAC enforcement + audit logging unit tests.

Pure-Python (no DB, no HTTP server) — runs in CI with no secrets.
Tests:
  - get_current_user_role()  extracts role from JWT or defaults to 'owner'
  - require_write_role()     raises 403 for auditor, passes for owner/accountant/admin
  - require_admin_role()     raises 403 for non-admin
  - _log_audit_event()       calls DB insert (mocked); is silent on DB failure
"""
from __future__ import annotations

import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt as pyjwt
from fastapi import HTTPException


# ── helpers ────────────────────────────────────────────────────────────────

def _make_token(role: str = "owner", secret: str = "test_secret_32_chars_long_enough!", expire_offset: int = 3600) -> str:
    return pyjwt.encode(
        {"userId": "u1", "sessionVersion": 1, "role": role, "exp": int(time.time()) + expire_offset},
        secret,
        algorithm="HS256",
    )


# ── get_current_user_role ─────────────────────────────────────────────────

def test_role_extracted_from_jwt(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="auditor")
    assert _app.get_current_user_role(f"Bearer {token}") == "auditor"


def test_role_missing_defaults_to_owner(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = pyjwt.encode({"userId": "u1"}, "test_secret_32_chars_long_enough!", algorithm="HS256")
    assert _app.get_current_user_role(f"Bearer {token}") == "owner"


def test_role_no_header_defaults_to_owner(monkeypatch):
    import app as _app
    assert _app.get_current_user_role(None) == "owner"


def test_role_invalid_token_defaults_to_owner(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    assert _app.get_current_user_role("Bearer not.a.valid.token") == "owner"


# ── require_write_role ────────────────────────────────────────────────────

def test_auditor_blocked_from_write(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="auditor")
    with pytest.raises(HTTPException) as exc_info:
        _app.require_write_role(f"Bearer {token}")
    assert exc_info.value.status_code == 403


def test_owner_passes_write(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="owner")
    _app.require_write_role(f"Bearer {token}")  # must not raise


def test_accountant_passes_write(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="accountant")
    _app.require_write_role(f"Bearer {token}")  # must not raise


def test_admin_passes_write(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="admin")
    _app.require_write_role(f"Bearer {token}")  # must not raise


def test_unknown_role_blocked(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="viewer")
    with pytest.raises(HTTPException) as exc_info:
        _app.require_write_role(f"Bearer {token}")
    assert exc_info.value.status_code == 403


# ── require_admin_role ────────────────────────────────────────────────────

def test_admin_passes_admin_check(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="admin")
    _app.require_admin_role(f"Bearer {token}")  # must not raise


def test_owner_blocked_from_admin(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="owner")
    with pytest.raises(HTTPException) as exc_info:
        _app.require_admin_role(f"Bearer {token}")
    assert exc_info.value.status_code == 403


def test_auditor_blocked_from_admin(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "JWT_SECRET", "test_secret_32_chars_long_enough!")
    monkeypatch.setattr(_app, "JWT_ALGORITHM", "HS256")
    token = _make_token(role="auditor")
    with pytest.raises(HTTPException) as exc_info:
        _app.require_admin_role(f"Bearer {token}")
    assert exc_info.value.status_code == 403


# ── _log_audit_event ──────────────────────────────────────────────────────

def test_log_audit_event_calls_db(monkeypatch):
    """When DATABASE_URL is set, _log_audit_event must attempt a DB insert."""
    import app as _app
    monkeypatch.setattr(_app, "DATABASE_URL", "postgresql://fake")
    inserted = []

    class _FakeCur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, *a, **kw): inserted.append(a[0])
    class _FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def cursor(self): return _FakeCur()
        def commit(self): pass

    monkeypatch.setattr(_app, "get_db_connection", lambda: _FakeConn())
    _app._log_audit_event("u1", "DOCUMENT_SAVED", "doc saved")
    assert len(inserted) == 1
    assert "ActivityLog" in inserted[0]


def test_log_audit_event_silent_on_db_failure(monkeypatch):
    """_log_audit_event must never raise even when the DB connection fails."""
    import app as _app
    monkeypatch.setattr(_app, "DATABASE_URL", "postgresql://fake")

    def _bad_conn():
        raise RuntimeError("DB down")

    monkeypatch.setattr(_app, "get_db_connection", _bad_conn)
    _app._log_audit_event("u1", "DOCUMENT_SAVED", "test")  # must not raise


def test_log_audit_event_skips_when_no_url(monkeypatch):
    """_log_audit_event must skip silently when DATABASE_URL is empty."""
    import app as _app
    monkeypatch.setattr(_app, "DATABASE_URL", "")
    called = []
    monkeypatch.setattr(_app, "get_db_connection", lambda: called.append(1))
    _app._log_audit_event("u1", "X", "content")
    assert called == []
