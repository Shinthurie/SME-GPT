# Iteration 15 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **PR:** shinthurie/iter-15-srs-gaps  
**Branch:** `shinthurie/iter-15-srs-gaps` (2 commits: `3f6933e`, `7ac39a1`)

## 1. Scope

Final SRS gap closure targeting FR-19, FR-30, FR-33, NFR-02/03/15 plus dev-environment
fixes for the Turbopack CSS resolution crash. Based on gap analysis from `docs/gap-analysis.md`.

### Backend changes

**`backend/pal_scope.py`** — `resolve_scope_with_rag()` (FR-19)
- Calls `vector_index.retrieve_top_k()` with `tenant_id=user_id` and `k=15` to retrieve
  semantically relevant chunk IDs via pgvector cosine similarity.
- Unions those IDs with the existing SQL-based `resolve_scope_with_c4()` result set, expanding
  the document scope when RAG finds relevant chunks that the SQL filter would have missed.
- Degrades silently to SQL-only scope when `ChunkEmbedding` has no rows for the tenant
  (pre-Iter9 documents) — no exception is raised.

**`backend/pal_qa.py`** — wires FR-19
- `answer_financial_question()` now calls `resolve_scope_with_rag(question, company_name, user_id)`
  instead of `resolve_scope()`. Signature change: 3-arg (question, company, user) vs old 2-arg.

**`backend/app.py`** — FR-33, NFR-02/03/15
- `GET /documents`: `page` and `limit` query parameters (NFR-02/03). Returns `pagination`
  object with `{page, limit, total, pages, has_next}`.
- `POST /ask-query`: logs `QUERY_EXECUTED` audit event after answer returned.
- `POST /process-document` (non-streaming): logs `DOCUMENT_UPLOAD` audit event.
- `DELETE /admin/audit-logs/prune`: admin-only endpoint to prune logs older than N days (NFR-15).

**`docker-compose.yml` + `nginx/nginx.conf` + `nginx/generate-certs.sh`** — FR-30
- Added `nginx` service to compose: exposes 80 and 443, backend/frontend use `expose` only.
- `nginx.conf`: HTTP→HTTPS redirect on port 80, TLS termination on 443 with TLSv1.2/1.3,
  proxy_pass to `frontend:3000` and `backend:8000`.
- `generate-certs.sh`: self-signed cert generation script (certs not committed; `nginx/certs/`
  in `.gitignore`).

### Frontend / dev-env changes

**`frontend/src/app/globals.css`** — Turbopack CSS fix
- Replaced bare `@import "tailwindcss"` with explicit layer imports:
  `tailwindcss/theme.css`, `tailwindcss/preflight.css`, `tailwindcss/utilities.css`.
  Prevents Turbopack walking up to `C:\Users\ASUS\package.json` (user home has a stale
  `{ dependencies: { docx } }` which caused OOM crash in dev).

**`frontend/next.config.ts`** — pure CJS rewrite
- Converted from ESM `import` statements to CJS `require()` so `__dirname` is defined.
- Sets `turbopack.root: __dirname` to pin Turbopack's module resolution root to `frontend/`.
- Conditionally wraps with `@ducanh2912/next-pwa` only in production build.

**`setup-dev.ps1`** — Windows junction helper
- Creates `<repo-root>/node_modules/tailwindcss` as a Windows junction pointing to
  `frontend/node_modules/tailwindcss`. Fallback for developers who run `npm run dev` from the
  repo root without the `turbopack.root` fix taking effect.
- Uses `mklink /J` (no admin elevation required).

### Test fix

**`backend/tests/test_iter5_pal_qa.py`**
- All 4 `monkeypatch.setattr` calls updated from `resolve_scope` (2-arg) to
  `resolve_scope_with_rag` (3-arg lambda `lambda _q, _company, _user: ...`).
  Without this fix the PAL QA tests were patching a function that no longer existed on the
  `pal_qa` module, causing `AttributeError` and 4 test failures.

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **255 passed, 1 transient DB failure** (`test_spatial_blobs_can_be_inserted_and_read` — Supabase connectivity; passes on retry), 0 test failures from code logic |
| `cd frontend && npx tsc --noEmit` | 0 errors |
| `cd frontend && npm run dev` (after running `setup-dev.ps1`) | Starts cleanly at `localhost:3000` in 660ms, no Turbopack OOM crash |
| `GET /documents?page=1&limit=10` | Returns `pagination.{page:1, limit:10, total:N, has_next:...}` correctly |

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| RAG scope hybrid | `retrieve_top_k` called before SQL scope; union returned | **verified** in `pal_scope.py`; degrades cleanly when `ChunkEmbedding` empty |
| FR-33 audit log | DOCUMENT_UPLOAD + QUERY_EXECUTED logged | **verified** in code; `ActivityLog` table receives entries |
| Pagination | `GET /documents?page=2&limit=5` returns correct slice | **verified** |
| Turbopack crash | `npm run dev` starts without OOM | **verified** — no more `Can't resolve 'tailwindcss'` |
| Test suite | ≥254 passing | **255 passing** |

## 4. Known gaps

- **Streaming endpoint DOCUMENT_UPLOAD**: the streaming `/process-document-stream` path now logs
  DOCUMENT_UPLOAD (added in this iteration), but the log fires at session-store time, not at
  actual DB confirm-save. A separate `DOCUMENT_SAVED` event fires at `/confirm-save`.
- **TLS certs not generated**: `nginx/certs/` is empty (gitignored). The nginx container will
  fail to start until `bash nginx/generate-certs.sh` is run on the deployment server.
  FR-30 is architecturally satisfied but needs one manual step before first deployment.
- **4 PAL QA tests were failing before this iteration** due to the signature change in Iter 15's
  own `pal_qa.py`. All fixed in commit `7ac39a1`.

## 5. Next

- Iterations 16 & 17: SRS UI mockup fidelity (Upload/Repository/Query/Answer/Analysis pages)
  and remaining backend gaps (FR-22, file_size_kb).
