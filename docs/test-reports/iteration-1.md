# Iteration 1 — Test Report

**Date:** 2026-06-22 · **Owner(s):** Ashfak (backend) · Shinthurie (DB review) · **PR:** (feat/iter-1-data-layer)

## 1. Scope
Replace the CSV store with the tenant-isolated Postgres schema on Supabase.

Delivered:
- Prisma models `FinancialDocument`, `LineItem`, `Entity`, `EntityAlias`, `DocLink`
  (`tenantId == User.id`); migrations `iter1_financial_and_c4` + `iter1_docdate_text`.
- Applied the 6 existing auth migrations + the 2 new ones to Supabase (restores auth tables).
- `prisma.config.ts` now loads `.env` via dotenv (Prisma 7 no longer auto-loads it).
- Backend `db.py` (psycopg connection helper) + rewritten `dataset_manager.py`
  (Postgres-backed, same public API and record shape; soft-delete; tenant-scoped).
- `data_tools.py` reads from Postgres (tenant-scoped) instead of CSV.
- `migrate_csv_to_db.py` — idempotent CSV→Postgres importer (dry-run by default, `--tenant` override).

## 2. Tests run
| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **6 passed** (1 smoke + 5 DB integration) |
| `migrate_csv_to_db.py` (dry run) | 11 rows parsed, 11 would insert, 0 errors |
| Prisma `migrate deploy` / `migrate dev` | all migrations applied to Supabase |

DB integration tests (run against Supabase; auto-skip when `DATABASE_URL` unset, e.g. CI):
- insert + read back (with line items)
- **tenant isolation** — tenant B cannot read/update/delete tenant A's document
- update (fields + line-item replacement)
- duplicate detection
- soft delete (row excluded from reads afterward)

Each test uses throwaway tenant ids and hard-deletes its rows in teardown.

## 3. Metrics
N/A (data-layer iteration). Tenant isolation verified by assertion.

## 4. Failures / known gaps
- **Old CSV data is not auto-imported.** The 11 legacy rows belong to old user ids that don't
  exist in the fresh Supabase DB. After registering, claim them with
  `python migrate_csv_to_db.py --tenant <user_id> --apply`.
- **`docDate` stored as text** (deviation from the approved `DateTime`): OCR dates are free-form
  strings; lossless text now, typed normalization deferred (needed for C3 date filters).
- **Backend `venv` is broken** locally (created against a removed `C:\Program Files\Python312`).
  Recreate it: `python -m venv venv && venv\Scripts\pip install -r requirements.txt`.
- DB integration tests are skipped in CI (no `DATABASE_URL` secret) — they run locally only.
- `app.py` write/read paths were repointed via the unchanged `dataset_manager` API but a full
  end-to-end app smoke (upload → save → query in the running app) is pending the user's re-login.

## 5. Next
- User: register on the new DB, confirm auth + dashboard load; optionally import old data.
- Iteration 2 (Component 1): box-level OCR correction + numeric safeguard.
