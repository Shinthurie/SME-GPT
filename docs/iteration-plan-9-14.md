# SME-GPT — Iterations 9–14: SRS Gap-Closure Plan

## Context

After 8 completed iterations, the SME-GPT SRS v1.2 has 33 functional requirements. All core AI modules (C1–C4, PAL QA, vector retrieval, entity index) are built and tested in isolation. The biggest remaining problem is that the live document pipeline still runs the old v1 text-blob flow — the new C1/C2/C3 modules are never invoked for real documents. This blocks ~10 FRs at once. The remaining gaps are: bbox overlays in UI, RBAC enforcement, admin panel, audit logging, deskew preprocessing, standardised errors, PWA support, and GDPR.

---

## Gap Inventory

| Gap | SRS FRs/NFRs Closed |
|---|---|
| GAP-A: C1+C2 not wired into live pipeline | FR-06, 07, 09, 13, 14, 15, 16, 17, 19, 22, 23 |
| GAP-B: No bbox overlay on document image | FR-24, 26, 27 |
| GAP-C: RBAC role stored but not enforced | FR-32 |
| GAP-D: No admin panel | SRS §4.1 (Admin screen) |
| GAP-E: Audit logging incomplete | FR-33, NFR-15 |
| GAP-F: No deskew in preprocessing | FR-03 |
| GAP-G: No PWA | N
FR-08 |
| GAP-H: No GDPR data export/deletion | NFR-14 |
| GAP-I: Inconsistent error responses | FR-04, FR-29 |

---

## Dependency Graph

```
Iter 9 (GAP-A)  →  Iter 10 (GAP-B)
Iter 11 (GAP-C + GAP-E)  →  Iter 12 (GAP-D + GAP-H)
Iter 13 (GAP-F + GAP-I)  — independent
Iter 14 (GAP-G)           — independent
```

Iterations 13 and 14 can run in parallel with 10–12.

---

## Iteration 9 — Wire C1+C2 into the Live Pipeline

**Goal:** Connect the built `spatial_serialization.build_spatial_chunks()` + vector embedding pipeline into the live `/process-document` → `/confirm-save` flow, persist `safeboxJson` and `spatialChunksJson` to the DB, and expose them from `GET /documents/{id}`.

**Approach (additive/safe):** The pipeline already calls `correct_boxes_for_page()` and `serialize_safe_boxes()`. Keep them. Add a second pass that calls `build_spatial_chunks()` using the already-produced `safe_boxes_by_page`, then calls `upsert_chunk_embeddings()` after confirm-save succeeds.

### Files to Modify

**`backend/document_pipeline.py`**
- In `build_preview_from_versions()`: after the existing C2 block, call `build_spatial_chunks()` from `spatial_serialization` with `tenant_id="__pending__"` and `document_id="__pending__"`. Add `"rich_spatial_chunks"` to the return dict.
- In `process_uploaded_document()`: forward `rich_spatial_chunks` in the return dict.

**`backend/app.py`**
- `/process-document` and `/process-document-stream`: store `safe_boxes` and `rich_spatial_chunks_template` in `PROCESSING_SESSIONS[session_id]["meta"]`.
- `/confirm-save` (after `upsert_confirmed_record` succeeds): patch the template with real `tenant_id` and `document_id`, call `flatten_chunks_for_embedding()` + `embed_rows(get_embedding_service())` + `upsert_chunk_embeddings()`. Add `safe_boxes_json` and `spatial_chunks_json` to the data dict before saving.
- `build_document_detail()`: include `safe_boxes_json` and `spatial_chunks_json` in the returned dict.

**`backend/dataset_manager.py`**
- Add `"safe_boxes_json"` and `"spatial_chunks_json"` to `DATASET_COLUMNS`, `RECORD_TO_DB`, and `JSON_FIELDS`.
- `normalize_record()`: default both to `"NULL"`.

**`frontend/prisma/schema.prisma`**
- Add to `FinancialDocument`:
  ```prisma
  safeboxJson       String?  @db.Text
  spatialChunksJson String?  @db.Text
  ```

**New migration:** `frontend/prisma/migrations/20260624000000_iter9_spatial_blobs/migration.sql`
```sql
ALTER TABLE "FinancialDocument" ADD COLUMN "safeboxJson" TEXT;
ALTER TABLE "FinancialDocument" ADD COLUMN "spatialChunksJson" TEXT;
```
Apply via psycopg (not Prisma CLI — PgBouncer transaction mode blocks DDL).

### Reuse
- `spatial_serialization.build_spatial_chunks()` — already tested, unchanged
- `vector_index.flatten_chunks_for_embedding()`, `embed_rows()`, `upsert_chunk_embeddings()` — already tested
- `embedding_service.get_embedding_service()` — returns `intfloat/multilingual-e5-small`
- `db.get_conn()` — existing helper

### New Tests: `backend/tests/test_iter9_pipeline_wiring.py`
- `test_c1_pages_format_conversion()` — convert `safe_boxes_by_page` to `[{"page": n, "boxes": [...]}]` and verify `build_spatial_chunks()` returns correct keys.
- `test_flatten_chunks_required_keys()` — verify `flatten_chunks_for_embedding` output has `tenant_id`, `document_id`, `chunk_id`, `page`, `bbox`, `chunk_type`, `text`.
- `test_skip_embed_when_no_safe_boxes()` — guard: empty `safe_boxes` → `upsert_chunk_embeddings` not called.
- DB integration test (skip without `DATABASE_URL`): upsert 2 mock rows → row count = 2.

### Exit Criteria
1. `pytest tests/test_iter9_pipeline_wiring.py` green.
2. Upload document → confirm-save → `ChunkEmbedding` has rows for that document.
3. `GET /documents/{id}` response contains non-null `spatial_chunks_json`.
4. Migration applied to Supabase without error.

**Size: M**

---

## Iteration 10 — Bbox Overlay Viewer

**Goal:** Replace the bare `<img>` in the document analysis page with an interactive SVG overlay that draws chunk bounding boxes and synchronises with the ProvenancePanel.

**Prerequisite:** Iteration 9 (`spatial_chunks_json` in API response).

### Files to Create

**`frontend/src/components/ui/BboxOverlayViewer.tsx`**
- Props: `imageUrl`, `documentId`, `spatialChunksJson?`, `onChunkSelect?`, `activeChunkId?`
- Wrap `<img>` in `<div style={{ position:"relative" }}>` + `<svg style={{ position:"absolute", inset:0, width:"100%", height:"100%" }}>` overlay.
- On `img.onLoad`, read `naturalWidth`/`naturalHeight` via `ref`.
- Parse `spatialChunksJson`: iterate `pages[].chunks[]` each with `provenance.bbox: [x1,y1,x2,y2]` in original-image pixel coords. Normalise: `x_pct = x1/imgW * 100`.
- Render `<rect>` elements. Active chunk gets highlighted stroke. Clicking calls `onChunkSelect(chunk_id)`.
- "Show Bboxes" toggle to avoid visual clutter.
- Graceful: if no `spatialChunksJson`, renders plain `<img>`.

### Files to Modify

**`frontend/src/app/analysis/[documentID]/page.tsx`**
- Add `spatial_chunks_json?: string | null` to `DocumentDetail` type.
- Add `activeChunkId` state.
- Import `BboxOverlayViewer` and replace the `<img>` block (lines ~357–376) with the new component.
- Pass `activeChunkId` + `onChunkSelect` down.

**`frontend/src/components/ui/ProvenancePanel.tsx`**
- Add optional `activeChunkId?: string | null` prop to highlight the matching field.

### Exit Criteria
1. `tsc --noEmit` passes.
2. Load document with image → coloured SVG bboxes appear over it.
3. Click a bbox → highlights the corresponding field in ProvenancePanel.
4. Old documents (null `spatial_chunks_json`) → plain image rendered, no errors.

**Size: M**

---

## Iteration 11 — RBAC Enforcement + Audit Logging

**Goal:** Enforce role-based write restrictions on destructive backend endpoints, encode `role` in the JWT, and fill audit log gaps in both frontend auth routes and backend document operations.

### Part 1: JWT + Backend RBAC

**`frontend/src/app/api/auth/login/route.ts`**
- Encode `role: user.role` in the `jwt.sign()` payload.

**`backend/app.py`**
- Add `get_current_user_role(authorization)` — decodes JWT and returns `payload.get("role", "owner")`.
- Add `require_write_role(authorization)` FastAPI dependency — raises `HTTPException(403)` if role not in `{"owner","accountant","admin"}`.
- Add `require_admin_role(authorization)` dependency — role must be `"admin"`.
- Inject `Depends(require_write_role)` on: `POST /confirm-save`, `PUT /documents/{id}`, `DELETE /documents/{id}`, `DELETE /query-history/{id}`, `DELETE /query-history`, `POST /process-document`, `POST /process-document-stream`.

### Part 2: Audit Logging

**`backend/app.py`**
- Add `_log_audit_event(user_id, event_type, content)` — inserts into `"ActivityLog"` table via `get_db_connection()` (existing psycopg helper at line ~70); silent on failure.
- Call in: `/confirm-save` → `DOCUMENT_SAVED`; `DELETE /documents/{id}` → `DOCUMENT_DELETED`; `PUT /documents/{id}` → `DOCUMENT_UPDATED`; 403 rejections → `RBAC_WRITE_DENIED`.

**`frontend/src/app/api/auth/signup/route.ts`** — log `SIGNUP` after `prisma.user.create()`.

**`frontend/src/app/api/auth/reset-password/route.ts`** — log `PASSWORD_RESET` after `prisma.user.update()`.

**`frontend/src/app/api/auth/logout/route.ts`** — decode JWT from cookie before clearing, log `LOGOUT`.

### New Tests: `backend/tests/test_iter11_rbac_enforcement.py`
- Auditor role → `require_write_role` raises 403.
- Owner role → no exception.
- JWT with `role` field → `get_current_user_role` returns it.
- JWT without `role` → defaults to `"owner"`.
- Mock DB → `_log_audit_event` called on document save.

### Exit Criteria
1. `pytest tests/test_iter11_rbac_enforcement.py` green.
2. `DELETE /documents/{id}` with auditor JWT → HTTP 403.
3. `/confirm-save` with owner JWT → success + `ActivityLog` has `DOCUMENT_SAVED` row.
4. `tsc --noEmit` passes.

**Size: M**

---

## Iteration 12 — Admin Panel + GDPR

**Goal:** Build the admin dashboard for user management and audit log viewing; add GDPR data export and account deletion endpoints.

**Prerequisite:** Iteration 11 (RBAC middleware must exist for admin-only routes).

### Admin Panel Files to Create

**`frontend/src/app/admin/page.tsx`**
- Client component. On mount: call `/api/auth/me`; redirect to `/dashboard` if `role !== "admin"`.
- Two tabs: **Users** (table + role dropdown using `PUT /api/admin/users`) and **Audit Logs** (table).

**`frontend/src/app/api/admin/users/route.ts`**
- `GET` — `getAuthenticatedUser()`, check admin, return `prisma.user.findMany({ select: {id, email, fullName, role, createdAt} })`.
- `PUT` — accept `{ userId, role }`, `prisma.user.update()`.

**`frontend/src/app/api/admin/audit-logs/route.ts`**
- `GET` — admin only, `prisma.activityLog.findMany({ include: { user: { select: { email: true } } }, take: 200, orderBy: { createdAt: "desc" } })`.

**`frontend/src/components/layout/BottomNav.tsx`** — conditionally render Admin nav item when `role === "admin"` (read from `/api/auth/me` or localStorage-cached value set at login).

### GDPR Files

**`backend/app.py`**
- `DELETE /user/account` — hard-delete all Postgres data for the user (`ChunkEmbedding`, `query_history`, `FinancialDocument`). Returns `{"success": true}`. The frontend must separately call its own delete route for the User record.
- `GET /user/export` — returns all user documents + query history as JSON using existing `load_all_records()` and `load_query_history_for_user()`.

**`frontend/src/app/api/user/delete/route.ts`**
- `DELETE` — `getAuthenticatedUser()`, `prisma.user.delete({ where: { id } })` (cascades to all related tables), clears `token` cookie.

**`frontend/src/app/profile/page.tsx`**
- Add "Danger Zone" section with:
  - "Export My Data" → `GET /user/export` with auth → `window.open(blobUrl)` to download JSON.
  - "Delete Account" → confirmation dialog → parallel calls to `DELETE /api/user/delete` + `DELETE /user/account` → redirect `/login`.

### Exit Criteria
1. `/admin` accessible to admin role only; shows Users + Audit Logs tabs.
2. Role update in admin panel persists on page refresh.
3. Profile page shows Export + Delete buttons.
4. Export → downloads JSON with user's documents and query history.
5. `tsc --noEmit` passes.

**Size: L**

---

## Iteration 13 — Deskew Preprocessing + Standardised Error Handling

**Goal:** Add skew correction before OCR to improve extraction quality on phone-photo documents; replace inconsistent per-endpoint exception handling with a global, structured error format.

### Deskew (GAP-F)

**`backend/requirements.txt`** — add `deskew`.

**`backend/document_pipeline.py`**
- Add `_deskew_image(img: np.ndarray) -> np.ndarray` using `determine_skew()` from `deskew` and `cv2.warpAffine`. Skip if `abs(angle) < 0.3°`.
- Call `img = _deskew_image(img)` in `preprocess_images()` immediately after `cv2.imread()` and before the resize step.

### Standardised Errors (GAP-I)

**`backend/app.py`**
- Add `ErrorResponse(BaseModel)` with `success: bool = False`, `error_code: str`, `message: str`.
- Add `@app.exception_handler(HTTPException)` — maps status codes to error codes (`401→UNAUTHORIZED`, `403→FORBIDDEN`, `404→DOCUMENT_NOT_FOUND`, `429→RATE_LIMITED`).
- Add `@app.exception_handler(Exception)` — logs stack trace server-side, returns `{"error_code":"INTERNAL_ERROR","message":"An unexpected error occurred."}` (never leaks `str(e)` to the client).
- Remove the per-route `except Exception as e: traceback.print_exc(); return JSONResponse(...)` blocks. Replace with `raise HTTPException(...)` where appropriate; the global handler catches the rest.

### New Tests: `backend/tests/test_iter13_deskew_errors.py`
- `test_deskew_trivial_angle_unchanged()` — image with 0° skew returns same array.
- `test_deskew_5deg_rotation_corrected()` — rotate a test numpy image by 5°, verify output angle reduced.
- `test_error_response_model_shape()` — serialise `ErrorResponse`, verify keys.
- `test_global_handler_hides_exception_message()` — `TestClient` call to a route that raises `Exception("secret_path")` → response body does not contain `"secret_path"`.
- `test_404_maps_to_correct_error_code()` — `GET /documents/FAKE` → `{"error_code":"DOCUMENT_NOT_FOUND"}`.

### Exit Criteria
1. `pytest tests/test_iter13_deskew_errors.py` green.
2. Upload a rotated invoice photo → extracted totals match the correct values.
3. Any API error returns `{"success":false,"error_code":"...","message":"..."}`.
4. No stack-trace content in any HTTP response body.

**Size: M**

---

## Iteration 14 — PWA Support

**Goal:** Make SME-GPT installable as a Progressive Web App (NFR-08): web manifest, app icons, and a service worker via `@ducanh2912/next-pwa`.

### Files to Create

**`frontend/public/manifest.json`**
```json
{
  "name": "SME-GPT",
  "short_name": "SME-GPT",
  "description": "Enterprise Document Intelligence",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563ff",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

**`frontend/public/icons/icon-192.png`** and **`icon-512.png`** — generate from the existing SVG logo or place manually.

### Files to Modify

**`frontend/package.json`** — add `"@ducanh2912/next-pwa": "^10.2.9"` to `dependencies`.

**`frontend/next.config.ts`** — wrap `nextConfig` with `withPWA({ dest: "public", disable: process.env.NODE_ENV === "development" })`.

**`frontend/src/app/layout.tsx`** — add to `<head>`:
```tsx
<link rel="manifest" href="/manifest.json" />
<meta name="theme-color" content="#2563ff" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<link rel="apple-touch-icon" href="/icons/icon-192.png" />
```
Update `metadata` export with `manifest: "/manifest.json"` and `themeColor: "#2563ff"`.

### Exit Criteria
1. `npm run build` succeeds; `public/sw.js` and `public/workbox-*.js` generated.
2. Chrome DevTools → Application → Manifest shows SME-GPT with icons.
3. Service worker shows as active in Chrome DevTools.
4. Lighthouse PWA score ≥ 90.
5. `tsc --noEmit` passes.

**Size: S**

---

## SRS Coverage After All Iterations

| FR | Status After Iters 9-14 |
|---|---|
| FR-01–05 | ✅ Already done |
| FR-06–09 | ✅ Iter 9 (stored in DB) |
| FR-10–12 | ✅ Already done |
| FR-13 | ✅ Iter 9 (page+bbox persisted) |
| FR-14–17 | ✅ Iter 9 (embeddings triggered) |
| FR-18–22 | ✅ Already done |
| FR-23 | ✅ Iter 9 (JSON blobs in DB) |
| FR-24, 26–27 | ✅ Iter 10 (bbox overlay) |
| FR-25 | ✅ Already done (DerivationTrace) |
| FR-28–29 | ✅ Iters 13+existing |
| FR-30–31 | 🟡 Supabase TLS/AES; documented |
| FR-32 | ✅ Iter 11 (enforced) |
| FR-33 | ✅ Iters 11+12 (comprehensive logs) |
| NFR-03 | 🟡 Postgres+indexes; scale untested |
| NFR-05 | 🟡 Ops/uptime; out of scope |
| NFR-07–09 | ✅ Iters 14+existing |
| NFR-13 | ✅ Already done (Dockerfiles) |
| NFR-14 | ✅ Iter 12 (export+delete) |
| NFR-15 | ✅ Iter 11+12 (comprehensive + retention note) |

---

## Verification Order

```
npm run build  (frontend)         — after every frontend iteration
pytest tests/  (backend, -q)      — after every backend iteration
tsc --noEmit  (frontend)          — after every frontend iteration
Manual: upload doc → confirm → GET /documents/{id} includes spatial_chunks_json  (Iter 9)
Manual: Chrome DevTools PWA audit  (Iter 14)
```
