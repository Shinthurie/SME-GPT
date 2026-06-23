# Iteration 11 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Ashfak · **PR:** (feat/iter-11-rbac-enforcement)

## 1. Scope

RBAC Enforcement + Audit Logging, per `docs/iteration-plan-9-14.md`'s Iteration 11 plan (written by
Shinthurie). Iteration 8 added the `User.role` column but never checked it anywhere — any logged-in
user, including `auditor` (meant to be read-only), could delete/edit any document. This closes that.

Delivered:

### Backend RBAC (`backend/app.py`)
- `_decode_token()` — shared JWT-decoding helper; `get_current_user_id()` refactored to use it
  (identical external behavior, same error messages, no regression).
- `get_current_user_role()` — returns the JWT's `role` claim, defaulting to `"owner"` for tokens
  issued before Iteration 8 (or any client that omits the claim) so existing sessions don't break.
- `require_write_role()` — raises 403 unless role is in `{owner, accountant, admin}` (`auditor` is
  read-only). Audit-logs `RBAC_WRITE_DENIED` before raising.
- `require_admin_role()` — raises 403 unless role is `"admin"`. Not wired into any route yet —
  reserved for the admin panel (Iteration 12).
- `_log_audit_event(user_id, event_type, content)` — best-effort `ActivityLog` insert; swallows any
  DB error so a logging failure can never turn a successful write into a 500 for the user.
- Wired `require_write_role()` into all 7 destructive endpoints from the plan: `POST
  /process-document`, `POST /process-document-stream`, `POST /confirm-save`, `PUT
  /documents/{id}`, `DELETE /documents/{id}`, `DELETE /query-history/{id}`, `DELETE
  /query-history`.
- Audit events: `DOCUMENT_SAVED` (`/confirm-save`), `DOCUMENT_UPDATED` (`PUT /documents/{id}`),
  `DOCUMENT_DELETED` (`DELETE /documents/{id}`), `RBAC_WRITE_DENIED` (any 403 from
  `require_write_role`/`require_admin_role`).

### Frontend (JWT + audit logging)
- `frontend/src/app/api/auth/login/route.ts` — `jwt.sign()` now includes `role: user.role`.
- `frontend/src/app/api/auth/signup/route.ts` — logs `SIGNUP` after `prisma.user.create()`
  (best-effort, wrapped so a log failure doesn't fail the signup response).
- `frontend/src/app/api/auth/reset-password/route.ts` — logs `PASSWORD_RESET` after
  `prisma.user.update()` (same best-effort pattern).
- `frontend/src/app/api/auth/logout/route.ts` — reads the `token` cookie *before* clearing it,
  decodes it to get `userId`, logs `LOGOUT`. An expired/invalid token just skips the log (logout
  still succeeds — the cookie always gets cleared).
- Regenerated the Prisma client (`npx prisma generate`) so `user.role` type-checks — Iteration 8's
  `role` column existed in the DB and `schema.prisma`, but the generated client was stale.

### Tests
- `backend/tests/test_iter11_rbac_enforcement.py` — 18 tests, against the *real* `app.py`
  functions (not a parallel reimplementation, unlike Iteration 8's RBAC unit tests) — this is the
  gap that let the Iteration 9 OCR-wiring bug ship un-caught, so this iteration's tests exercise
  the actual guards directly.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **242 passed** (full suite, including the live Supabase round-trip test) |
| `cd backend && ruff check app.py tests/test_iter11_rbac_enforcement.py` | clean (pre-existing `E402` import-order findings elsewhere in `app.py` unrelated to this change) |
| `cd frontend && npx tsc --noEmit` | 0 errors (after `npx prisma generate`) |
| Live `/documents/{id}` DELETE smoke test via `fastapi.testclient.TestClient`, real signed JWTs, `delete_record_for_user` mocked | auditor role → **403** with the expected message; owner role → **200** success; both correctly attempted the audit-log write (failed gracefully on a synthetic non-existent user, proving `_log_audit_event`'s error-swallowing works in practice, not just in the mocked unit test) |

New tests cover:
- `get_current_user_id`/`get_current_user_role`: claim extraction, missing-header 401, missing-role
  claim defaults to `"owner"`.
- `require_write_role`: accepts `owner`/`accountant`/`admin`, rejects `auditor` and any unknown
  role with 403, and logs `RBAC_WRITE_DENIED` (verified via monkeypatching `_log_audit_event`).
- `require_admin_role`: accepts `admin` only, rejects every other role with 403.
- `_log_audit_event`: issues the correct `INSERT` (hermetic, fake cursor/connection — no DB
  needed), swallows DB errors without raising, no-ops when `DATABASE_URL` is unset.
- Live round trip: inserts a throwaway `User` row (required — `ActivityLog.userId` has a real FK
  to `User.id`, unlike `tenantId` elsewhere in the schema, which is a bare string), logs an event,
  reads it back, then deletes the user (cascades to the log row per `onDelete: Cascade`).

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| RBAC enforcement coverage | all destructive endpoints | **7/7** — every endpoint named in the Iteration 11 plan now calls `require_write_role` |
| Audit-log failure isolation | a log failure must never break the operation it's logging | **verified** — both the hermetic test and the live smoke test confirm `_log_audit_event` swallows errors (FK violation in the smoke test, monkeypatched `RuntimeError` in the unit test) without the request failing |
| Backward compatibility | existing sessions (pre-RBAC JWTs) keep working | **verified** — `get_current_user_role` defaults to `"owner"` (a write role) when the claim is absent, so users who logged in before this change aren't locked out |

## 4. Known gaps

- **`require_admin_role` is unused** until Iteration 12's admin panel exists.
- **Audit logging doesn't cover reads** (`GET /documents`, `GET /documents/{id}`, etc.) — only
  writes and RBAC denials, per the plan's scope.
- **No retention policy** — `ActivityLog` rows accumulate indefinitely; a 1-year auto-delete job
  (NFR-15) is still a follow-up, same as flagged in Iteration 8's report.
- **`/process-document` and `/process-document-stream` reject before their `try` block** — same as
  `get_current_user_id` already did before this change (not a new pattern), so an 401/403 there
  returns FastAPI's default JSON error shape rather than this app's `{"success": false, ...}`
  convention. Pre-existing inconsistency, not introduced here; Iteration 13's planned global
  exception handler (GAP-I) will standardize this.

## 5. Next

- Iteration 12 (Admin Panel + GDPR) can now build on `require_admin_role`.
- Iteration 13's standardized error handler should also normalize the 401/403 shape from routes
  that check auth before their `try` block.
