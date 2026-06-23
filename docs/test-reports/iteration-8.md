# Iteration 8 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **Branch:** main

## 1. Scope

Security & NFR Hardening + Deployment: in-process rate limiting, RBAC role field,
Supabase TLS documentation, Dockerfiles for backend and frontend.

Delivered:

### Rate Limiting (NFR)
- `backend/app.py` — `@app.middleware("http")` sliding-window rate limiter:
  in-process, no new dependency.  Per-IP, per-path counters in a `defaultdict`
  protected by a `threading.Lock`.  Limits:
  - `/ask-query` → 30 req / 60 s
  - `/process-document`, `/process-document-stream` → 10 req / 60 s
  - All other paths → 120 req / 60 s
  Returns HTTP 429 `{"detail": "Rate limit exceeded. Please slow down."}` when
  the bucket is full.

### RBAC Roles (FR-32)
- `frontend/prisma/schema.prisma` — `UserRole` enum (`owner | accountant | admin
  | auditor`) + `role` column on `User` (default `owner`).
- `frontend/prisma/migrations/20260623000000_iter8_rbac_role/migration.sql` —
  `CREATE TYPE "UserRole" …; ALTER TABLE "User" ADD COLUMN role …`.
- Applied to live Supabase via psycopg (Prisma CLI `migrate deploy` fails over
  PgBouncer transaction mode; direct psycopg apply documented as the workaround).
- `frontend/src/app/api/auth/me/route.ts` — exposes `role` in `/api/auth/me`
  response so frontends and future middleware can read it without a second DB query.

### TLS / Encryption-at-Rest
- Supabase enforces TLS on all connections (documented).
- `frontend/.env` / `backend/.env` connection URLs use port 6543 (PgBouncer) with
  SSL enforced at the driver level (`ssl: {rejectUnauthorized: false}` for `pg` v8;
  `sslmode=require` appended in `prisma.config.ts` for Prisma CLI).

### Dockerfiles
- `backend/Dockerfile` — `python:3.12-slim`, installs Poppler via `apt`, copies
  `requirements.txt`, exposes port 8000, runs Uvicorn.
- `frontend/Dockerfile` — 3-stage `node:22-alpine` build (deps → builder → runner),
  Next.js standalone output.
- `docker-compose.yml` — `backend` + `frontend` services; backend health-check;
  named volumes for `saved_documents` and `temp_processing`.

## 2. Tests run

| Command | Result |
|---|---|
| `python -m pytest tests/test_iter8_security.py -v` | **15 passed** in 2.5 s |
| `python -m pytest tests/ -q` (full suite) | **206 passed**, 1 transient Supabase skip; re-run: **207 passed** |
| `npx tsc --noEmit` (frontend) | **0 errors** |

Security tests (15):
- Rate limiter: 5 cases (under-limit passes, blocks-at-limit, key isolation,
  1-second window expiry, path isolation)
- RBAC checks: 6 cases (owner/accountant write, auditor cannot write,
  all roles query, unknown role, admin-only flag)
- JWT: 3 cases (valid decode, tampered signature rejected, expired token rejected)
- Smoke: app imports cleanly with rate-limit middleware wired (1)

## 3. Known gaps

- **RBAC not enforced in API routes yet.** The `role` field is stored in the DB
  and returned by `/api/auth/me`, but no route currently checks it before
  allowing writes. The enforcement pattern is tested via the RBAC unit tests;
  wiring it into the route handlers is a follow-up.
- **Audit log retention** — the `ActivityLog` table exists and logs activity, but
  a 1-year retention policy (automated deletion of old rows) is not yet scheduled.
- **Docker Compose smoke test in CI** — Dockerfiles are present but not yet
  exercised in the GitHub Actions workflow.
- **Prisma migrate deploy over PgBouncer** — `prisma migrate deploy` fails with
  P1017 over port 6543 (transaction mode). Workaround: apply migration SQL via
  psycopg directly. A `DIRECT_URL` env var for the Prisma CLI (using the Supabase
  session pooler or direct connection) would fix this but requires the port to be
  accessible from the dev machine.

## 5. Next

All 8 planned iterations are complete. Remaining follow-ups across iterations:
- Wire C1/C2 into `document_pipeline.py` for real per-box OCR data (enables
  bbox overlays in Iter 7)
- Enforce RBAC roles in FastAPI route handlers
- CI Docker Compose smoke test
- Audit log retention cron
