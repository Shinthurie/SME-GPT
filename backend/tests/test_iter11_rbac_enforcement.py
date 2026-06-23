"""Iteration 11 — RBAC enforcement + audit logging tests.

Covers: `_decode_token`/`get_current_user_id`/`get_current_user_role` (JWT
claim extraction), `require_write_role`/`require_admin_role` (the allow-list
guards gating destructive endpoints), and `_log_audit_event` (best-effort
ActivityLog writes). The role/JWT logic is tested directly against the real
functions in `app.py` (not a parallel reimplementation) with a real signed
token, so these tests prove the actual guards behave correctly -- this is
the gap that let Iteration 9's OCR-wiring bug ship un-caught.

DB-touching tests are split the same way as the rest of the suite: a
hermetic test fakes `get_db_connection` to verify `_log_audit_event` issues
the right INSERT without a real database, and one DB-integration test (the
real round trip) is skipped when `DATABASE_URL` is unset, same pattern as
`tests/test_iter1_data_layer.py`.
"""
from __future__ import annotations

import os

import pytest

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass


@pytest.fixture(scope="module")
def app_module():
    import app as app_mod
    return app_mod


def _token(app_module, **claims):
    import jwt as pyjwt
    return pyjwt.encode(claims, app_module.JWT_SECRET, algorithm=app_module.JWT_ALGORITHM)


def _bearer(app_module, **claims):
    return f"Bearer {_token(app_module, **claims)}"


# ---------------------------------------------------------------------------
# get_current_user_id / get_current_user_role
# ---------------------------------------------------------------------------

def test_get_current_user_id_extracts_claim(app_module):
    auth = _bearer(app_module, userId="user-1")
    assert app_module.get_current_user_id(auth) == "user-1"


def test_get_current_user_id_missing_header_raises_401(app_module):
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.get_current_user_id(None)
    assert exc.value.status_code == 401


def test_get_current_user_role_returns_role_from_token(app_module):
    auth = _bearer(app_module, userId="user-1", role="accountant")
    assert app_module.get_current_user_role(auth) == "accountant"


# ---------------------------------------------------------------------------
# sessionVersion enforcement (mirrors frontend/src/lib/auth-server.ts) --
# makes a password reset invalidate a leaked Bearer token on the backend
# too, not just the Next.js cookie session.
# ---------------------------------------------------------------------------

def test_decode_token_accepts_matching_session_version(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_get_session_version", lambda user_id: 3)
    auth = _bearer(app_module, userId="user-1", sessionVersion=3)
    assert app_module.get_current_user_id(auth) == "user-1"


def test_decode_token_rejects_stale_session_version(app_module, monkeypatch):
    """A password reset bumps User.sessionVersion -- a token signed before
    that (still carrying the old value) must be rejected."""
    monkeypatch.setattr(app_module, "_get_session_version", lambda user_id: 4)
    auth = _bearer(app_module, userId="user-1", sessionVersion=3)
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.get_current_user_id(auth)
    assert exc.value.status_code == 401


def test_decode_token_rejects_when_user_no_longer_exists(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_get_session_version", lambda user_id: None)
    auth = _bearer(app_module, userId="deleted-user", sessionVersion=1)
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.get_current_user_id(auth)
    assert exc.value.status_code == 401


def test_decode_token_fails_closed_on_db_error(app_module, monkeypatch):
    """If the session-version lookup itself fails (DB down), deny rather
    than silently skipping the check."""
    def _boom(user_id):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(app_module, "_get_session_version", _boom)
    auth = _bearer(app_module, userId="user-1", sessionVersion=1)
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.get_current_user_id(auth)
    assert exc.value.status_code == 401


def test_decode_token_skips_check_when_claim_absent(app_module, monkeypatch):
    """Tokens without a sessionVersion claim at all (shouldn't happen with
    either current login path, but defensive) skip the DB check entirely
    rather than failing -- same graceful-degradation approach as the missing
    `role` claim defaulting to 'owner'."""
    called = []
    monkeypatch.setattr(app_module, "_get_session_version", lambda user_id: called.append(user_id))
    auth = _bearer(app_module, userId="user-1")
    assert app_module.get_current_user_id(auth) == "user-1"
    assert called == []


def test_get_current_user_role_defaults_to_owner_when_missing(app_module):
    """Tokens issued before RBAC roles existed (Iteration 8) have no `role`
    claim at all -- must not break, must default to the least-surprising
    role (owner), not silently lock existing users out."""
    auth = _bearer(app_module, userId="user-1")
    assert app_module.get_current_user_role(auth) == "owner"


# ---------------------------------------------------------------------------
# require_write_role
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["owner", "accountant", "admin"])
def test_require_write_role_allows_write_roles(app_module, role):
    auth = _bearer(app_module, userId="user-1", role=role)
    assert app_module.require_write_role(auth) == role


def test_require_write_role_rejects_auditor(app_module):
    auth = _bearer(app_module, userId="user-1", role="auditor")
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.require_write_role(auth)
    assert exc.value.status_code == 403


def test_require_write_role_rejects_unknown_role(app_module):
    auth = _bearer(app_module, userId="user-1", role="totally_made_up")
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.require_write_role(auth)
    assert exc.value.status_code == 403


def test_require_write_role_logs_audit_event_on_denial(app_module, monkeypatch):
    logged = []
    monkeypatch.setattr(app_module, "_log_audit_event", lambda user_id, event_type, content: logged.append((user_id, event_type, content)))

    auth = _bearer(app_module, userId="user-42", role="auditor")
    with pytest.raises(app_module.HTTPException):
        app_module.require_write_role(auth)

    assert len(logged) == 1
    user_id, event_type, content = logged[0]
    assert user_id == "user-42"
    assert event_type == "RBAC_WRITE_DENIED"
    assert "auditor" in content


# ---------------------------------------------------------------------------
# require_admin_role
# ---------------------------------------------------------------------------

def test_require_admin_role_allows_admin(app_module):
    auth = _bearer(app_module, userId="user-1", role="admin")
    assert app_module.require_admin_role(auth) == "admin"


@pytest.mark.parametrize("role", ["owner", "accountant", "auditor"])
def test_require_admin_role_rejects_non_admin(app_module, role):
    auth = _bearer(app_module, userId="user-1", role=role)
    with pytest.raises(app_module.HTTPException) as exc:
        app_module.require_admin_role(auth)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# _log_audit_event (hermetic -- fakes the DB connection)
# ---------------------------------------------------------------------------

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


def test_log_audit_event_issues_insert_with_expected_fields(app_module, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: _FakeConn(calls))

    app_module._log_audit_event("user-1", "DOCUMENT_SAVED", "document_id=INV1")

    assert len(calls) == 1
    query, params = calls[0]
    assert '"ActivityLog"' in query
    assert params[1] == "user-1"
    assert params[2] == "DOCUMENT_SAVED"
    assert params[3] == "document_id=INV1"


def test_log_audit_event_swallows_db_errors(app_module, monkeypatch):
    """A logging failure must never propagate -- it would otherwise turn a
    successful document save/delete into a 500 for the user."""
    monkeypatch.setattr(app_module, "DATABASE_URL", "postgresql://fake")

    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(app_module, "get_db_connection", _boom)

    app_module._log_audit_event("user-1", "DOCUMENT_SAVED", "should not raise")


def test_log_audit_event_noop_without_database_url(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE_URL", "")
    called = []
    monkeypatch.setattr(app_module, "get_db_connection", lambda: called.append(1))

    app_module._log_audit_event("user-1", "DOCUMENT_SAVED", "x")

    assert called == []


# ---------------------------------------------------------------------------
# Live DB round trip (skipped without DATABASE_URL)
# ---------------------------------------------------------------------------

pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping ActivityLog integration test",
)


@pytestmark_db
def test_log_audit_event_persists_and_is_readable(app_module):
    import uuid

    import db

    # ActivityLog.userId has a real FK to User.id -- need a throwaway row to
    # satisfy it (unlike tenantId elsewhere in the schema, which is a bare
    # string with no FK).
    test_user_id = f"test_{uuid.uuid4().hex}"
    with db.get_conn() as conn:
        conn.cursor().execute(
            'INSERT INTO "User" (id, email, password, "updatedAt") VALUES (%s, %s, %s, NOW())',
            (test_user_id, f"{test_user_id}@example.test", "unused"),
        )

    try:
        app_module._log_audit_event(test_user_id, "DOCUMENT_SAVED", "integration test row")

        with db.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT type, content FROM "ActivityLog" WHERE "userId" = %s',
                (test_user_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row["type"] == "DOCUMENT_SAVED"
        assert row["content"] == "integration test row"
    finally:
        with db.get_conn() as conn:
            # Cascades to ActivityLog (onDelete: Cascade in schema.prisma).
            conn.cursor().execute('DELETE FROM "User" WHERE id = %s', (test_user_id,))


@pytestmark_db
def test_session_version_check_against_real_db(app_module):
    """End-to-end: a token signed with the user's current sessionVersion
    works; after bumping sessionVersion (what reset-password now does), the
    same token is rejected -- proving the backend half of the password-reset
    session-invalidation fix actually works against the real schema."""
    import uuid

    import db

    test_user_id = f"test_{uuid.uuid4().hex}"
    with db.get_conn() as conn:
        conn.cursor().execute(
            'INSERT INTO "User" (id, email, password, "sessionVersion", "updatedAt") '
            "VALUES (%s, %s, %s, %s, NOW())",
            (test_user_id, f"{test_user_id}@example.test", "unused", 1),
        )

    try:
        auth = _bearer(app_module, userId=test_user_id, sessionVersion=1)
        assert app_module.get_current_user_id(auth) == test_user_id

        with db.get_conn() as conn:
            conn.cursor().execute(
                'UPDATE "User" SET "sessionVersion" = "sessionVersion" + 1 WHERE id = %s',
                (test_user_id,),
            )

        with pytest.raises(app_module.HTTPException) as exc:
            app_module.get_current_user_id(auth)
        assert exc.value.status_code == 401
    finally:
        with db.get_conn() as conn:
            conn.cursor().execute('DELETE FROM "User" WHERE id = %s', (test_user_id,))
