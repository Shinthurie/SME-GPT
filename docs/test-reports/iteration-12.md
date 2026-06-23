# Iteration 12 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Ashfak · **PR:** (feat/iter-12-admin-gdpr)

## 1. Scope

Admin Panel + GDPR data export/deletion, per `docs/iteration-plan-9-14.md`'s Iteration 12 plan.
Depends on Iteration 11's `require_admin_role` (built but unwired until now).

Delivered:

### Backend GDPR (`backend/app.py`)
- `GET /user/export` — returns the caller's `FinancialDocument` records (via existing
  `load_all_records()`) and `query_history` rows (via existing `load_query_history_for_user()`) as
  one JSON payload, plus an `exported_at` timestamp.
- `DELETE /user/account` — hard-deletes every tenant-scoped row the backend owns directly via
  psycopg: `DocLink`, `ChunkEmbedding`, `Entity` (cascades `EntityAlias`), `FinancialDocument`
  (cascades `LineItem`), `query_history`. Scoped only to the caller's own `tenantId`/`user_id` —
  every statement is parameterized, never an unscoped wipe. No RBAC gate beyond authentication: any
  authenticated user can export/delete *their own* data regardless of role (a GDPR right, not a
  write privilege). Unlike `_log_audit_event`, a DB error here surfaces as a 500 rather than being
  swallowed — silently reporting success on a failed wipe would be the wrong failure mode for a
  "delete my data" request.
- Extended the tenant-scoped table list beyond the plan's three named tables (`ChunkEmbedding`,
  `query_history`, `FinancialDocument`) to also cover `DocLink` and `Entity`/`EntityAlias`
  (Iteration 4's C4 relationship-index tables) — both are tenant-scoped via the same
  `tenantId == User.id` convention and would otherwise be orphaned by an account deletion.

### Frontend Admin Panel
- `frontend/src/app/api/admin/users/route.ts` — `GET` (admin-only, lists all users) and `PUT`
  (admin-only, updates a user's role; logs `ADMIN_ROLE_CHANGED` to `ActivityLog`).
- `frontend/src/app/api/admin/audit-logs/route.ts` — `GET` (admin-only, latest 200 `ActivityLog`
  rows with the acting user's email).
- `frontend/src/app/admin/page.tsx` — client page, redirects non-admins to `/dashboard`; Users tab
  (role dropdown per row) and Audit Logs tab.
- `frontend/src/components/layout/BottomNav.tsx` — adds a 5th "Admin" tab (grid-cols-5) only when
  `/api/auth/me` reports `role === "admin"`.

### Frontend GDPR
- `frontend/src/app/api/user/delete/route.ts` — `DELETE`, `prisma.user.delete()` (cascades
  `TrustedDevice`/`LoginVerification`/`ActivityLog`/`UploadedFile` per `onDelete: Cascade`), clears
  the `token` cookie using the same expiry pattern as `logout/route.ts`.
- `frontend/src/app/profile/page.tsx` — "Danger Zone" section: **Export My Data** (calls the
  backend's `/user/export` with the stored Bearer token, downloads the JSON as a file) and **Delete
  Account** (inline confirm step, then calls the frontend's `/api/user/delete` and the backend's
  `/user/account` in parallel before redirecting to `/login`).

### Tests
- `backend/tests/test_iter12_gdpr_endpoints.py` — 6 tests against the real `app.py` routes via
  `TestClient` (not a parallel reimplementation), same convention as Iteration 11.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **254 passed** (full suite, including the live Supabase round-trip test for account deletion) |
| `cd frontend && npx tsc --noEmit` | 0 errors |
| `cd frontend && npm run build` | Compiled successfully; all routes (including new `/admin`, `/api/admin/*`, `/api/user/delete`) built without errors |

New tests cover:
- `GET /user/export`: 401 without auth; returns `documents`/`query_history`/`exported_at` for the
  authenticated caller (mocked `load_all_records`/`load_query_history_for_user`).
- `DELETE /user/account`: 401 without auth; issues a `DELETE` against every tenant-scoped table
  (`DocLink`, `ChunkEmbedding`, `Entity`, `FinancialDocument`, `query_history`), every statement
  parameterized to `(user_id,)` only — verified hermetically against a fake DB connection; a DB
  error surfaces as a 500 (not swallowed, unlike `_log_audit_event`).
- Live round trip (skipped without `DATABASE_URL`, ran here against the real Supabase instance):
  inserts a throwaway `User` + `FinancialDocument` row, calls `delete_user_account()`, confirms the
  document row is gone.

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Admin routes gated | `/admin` + both `/api/admin/*` routes | **3/3** — all check `role === "admin"`, redirecting/403-ing otherwise |
| GDPR table coverage | every tenant-scoped Postgres table reachable by `tenantId`/`user_id` | **6/6** including the two (`DocLink`, `Entity`/`EntityAlias`) not explicitly named in the iteration plan |
| Backend test suite | green | **254/254** |

## 4. Known gaps

- **No pagination on `/api/admin/audit-logs`** — capped at the most recent 200 rows per the plan;
  fine for current data volume, would need a `cursor`/`skip` param at scale.
- **Account deletion is not transactional across both calls** — the frontend's `/api/user/delete`
  (User + Prisma-cascaded tables) and the backend's `/user/account` (psycopg-owned tables) run as
  two independent requests from the browser. If one succeeds and the other fails, the account is
  left partially deleted; the UI surfaces a generic failure message but doesn't retry or roll back.
  A follow-up could have the frontend route call the backend internally so it's one atomic-ish
  operation from the user's perspective, or queue a cleanup job.
- **Audit logging for GDPR actions** — `/user/export` and `/user/account` don't write `ActivityLog`
  rows (logging a deletion to a table you're about to delete is moot for the account-owner's own
  log; an `ADMIN`-visible record of "user X exported/deleted their data" wasn't in the plan's
  exit criteria, but could matter for compliance evidence later).

## 5. Next

- Iteration 13 (Deskew + standardized errors) and Iteration 14 (PWA) are independent and can start
  in either order.
