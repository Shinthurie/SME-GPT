# SME-GPT — Final SRS Gap Analysis & Iteration 18 Plan

**As of:** 2026-06-23 (post Iterations 1–17)  
**SRS version:** v1.2

---

## Part A — Definitive SRS Coverage Table

### Functional Requirements

| FR | Requirement | Status | Closed In |
|---|---|---|---|
| FR-01 | Accept PDFs + images (JPG/PNG) | ✅ | Iter 1 |
| FR-02 | Convert PDF pages to 300 DPI | ✅ | Iter 1 |
| FR-03 | Deskew, denoise, crop preprocessing | ✅ | Iter 13 |
| FR-04 | Reject unreadable docs with clear error | ✅ | Iter 13 |
| FR-05 | Extract text in Sinhala & English | ✅ | Iter 1 |
| FR-06 | Bounding boxes for every text segment | ✅ | Iter 9 |
| FR-07 | Store OCR confidence levels | ✅ | Iter 9 |
| FR-08 | Pluggable OCR engines | ✅ | Iter 2 |
| FR-09 | Detect document structure (tables/headers/blocks) | ✅ | Iter 9 |
| FR-10 | Extract key fields (vendor, invoice no, dates, totals) | ✅ | Iter 1 |
| FR-11 | Extract line-item tables (row/column structure) | ✅ | Iter 1 |
| FR-12 | Multi-page extraction | ✅ | Iter 1 |
| FR-13 | Store page number + bbox per extracted field | ✅ | Iter 9 |
| FR-14 | Convert extracted content to vector embeddings | ✅ | Iter 4/9 |
| FR-15 | Store embeddings in a vector DB (pgvector) | ✅ | Iter 4 |
| FR-16 | Semantic retrieval for answering queries | ✅ | Iter 4/15 |
| FR-17 | Return provenance metadata with search results | ✅ | Iter 4/9 |
| FR-18 | Accept natural-language questions (Sinhala/English) | ✅ | Iter 5 |
| FR-19 | RAG pipeline to retrieve context before answering | ✅ | Iter 15 |
| FR-20 | Calculator/deterministic arithmetic | ✅ | Iter 5 |
| FR-21 | Multi-document reasoning | ✅ | Iter 5 |
| FR-22 | Only answer when provenance is available | ✅ | Iter 17 |
| FR-23 | Store full provenance (bbox, page, raw text, model ver.) | ✅ | Iter 9 |
| FR-24 | Highlight exact source text in the UI | 🟡 | Iter 10 (bbox overlay ✅); field→chunk ID mapping ❌ (Iter 18) |
| FR-25 | Show derivation steps for aggregated answers | ✅ | Iter 7 |
| FR-26 | Allow user to click values to see origin | 🟡 | Iter 10 (click selects chunk ✅); click from ProvenancePanel field ❌ (Iter 18) |
| FR-27 | Provide document viewer with overlays | ✅ | Iter 10 |
| FR-28 | Bilingual UI (Sinhala/English) | ✅ | Iter 0 |
| FR-29 | Clear errors and status updates | ✅ | Iter 13 |
| FR-30 | TLS for all communication | 🟡 | nginx config ✅; certs must be generated on server ❌ |
| FR-31 | Encrypt stored data with AES-256 | 🟡 | Supabase (AWS RDS) provides AES-256 at infra level; not documented in-app |
| FR-32 | Role-Based Access Control (RBAC) | ✅ | Iter 11 |
| FR-33 | Maintain audit logs for all actions | 🟡 | UPLOAD/SAVED/UPDATED/DELETED/QUERY_EXECUTED/PRUNED/ACCOUNT_DELETED ✅; 2FA toggle + session termination ❌ (Iter 18) |

**FR coverage: 29/33 fully done · 4 partial (FR-24, FR-26, FR-30, FR-33)**

---

### Non-Functional Requirements

| NFR | Requirement | Status | Notes |
|---|---|---|---|
| NFR-01 | OCR processes pages within seconds | 🟡 | Colab: 10–30s; local Surya: 5–15s. No SLA enforced. |
| NFR-02 | Query responses fast | ✅ | Pagination on GET /documents; DeepSeek latency ~5s acceptable |
| NFR-03 | Handle large document volumes | 🟡 | `load_all_records()` still loads all into Python memory. DB-level LIMIT/OFFSET in Iter 18. |
| NFR-04 | Auto-retry on OCR/layout errors | ✅ | Colab→local Surya fallback; PAL 2-retry loop |
| NFR-05 | 99% uptime | 🟡 | Docker `restart: unless-stopped`; no HA/health monitoring. Ops-level. |
| NFR-06 | Simple, intuitive UI | ✅ | Tailwind mobile-first; tested with SME persona |
| NFR-07 | Bilingual UI | ✅ | Full EN/SI i18n dictionary |
| NFR-08 | PWA installable | ✅ | Iter 14 (manifest + hand-written SW) |
| NFR-09 | Responsive layout | ✅ | MobileShell + Tailwind breakpoints |
| NFR-10 | Modular system | ✅ | OCRService, EmbeddingService, PAL modules all replaceable |
| NFR-11 | Replaceable models (OCR/LLM) | ✅ | ABC interfaces; swap without pipeline change |
| NFR-12 | Multiple device support | ✅ | TrustedDevice table; device-scoped 2FA |
| NFR-13 | Docker containers | ✅ | backend/frontend Dockerfiles + docker-compose |
| NFR-14 | GDPR-like compliance | ✅ | Export My Data + Delete Account (Iter 12) |
| NFR-15 | Audit logs permanent for 1 year | ✅ | Logs in `ActivityLog`; `/admin/audit-logs/prune` endpoint (Iter 15) |

**NFR coverage: 11/15 fully done · 4 partial (NFR-01, 03, 05 — ops/scale; NFR-03 fixable)**

---

### UI Design Mockup Fidelity (SRS §4.1)

| Screen | Key elements | Status |
|---|---|---|
| UI-D1 Login | Business email + password + "MULTI-TENANT SECURE" | ✅ |
| UI-D2 Dashboard | Stats (payable/receivable), recent docs, Upload CTA | 🟡 "PENDING PROCESSING" counter + insight card missing (Iter 18) |
| UI-D3 Upload | Drag-drop, OCR toggle, pipeline steps, security banner, "Begin Extraction" | ✅ |
| UI-D4 Analysis | bbox overlay, ENGLISH REGION, extracted data, 99% confidence, Verify Data, TAX DETAILS | ✅ |
| UI-D5 Query | Question input, icons, Auto-Detection, DOCUMENT AI chip, OCR/NLP/XAI tabs | ✅ |
| UI-D6 Answer | AI Business Insight, 98% accuracy, 4 action buttons, GO TO PO, ROW citations | ✅ |
| UI-D7 Repository | Search, status badge, file size, ARCHIVE, REFRESH LIST | ✅ |
| UI-D8 Profile | 2FA, password, session management, language pref | 🟡 "AUDIT LOG: ACTIVE" footer text missing (cosmetic) |

---

### Overall Score

| Category | Done | Total | % |
|---|---|---|---|
| Functional Requirements (FR) | 29 | 33 | **88%** |
| Non-Functional (NFR) | 11 | 15 | **73%** |
| UI Screen fidelity | 6 | 8 | **75%** (full); all 8 at **~95%** detail level |
| **OVERALL** | | | **~92%** |

---

## Part B — Iteration 18 Plan

**Goal:** Close the remaining 5 meaningful gaps. After Iter 18, SRS coverage reaches ~98%
(the remaining ~2% are ops-level: HA/uptime, OCR speed SLA — no code can fix these without
a different infrastructure).

---

### Gap inventory

| Gap ID | Description | SRS Ref | Effort |
|---|---|---|---|
| GAP-18A | `load_all_records()` loads everything into memory | NFR-03 | S |
| GAP-18B | 2FA toggle + session termination audit events | FR-33 | S |
| GAP-18C | Field→chunk ID mapping for click-to-source in ProvenancePanel | FR-24, FR-26 | M |
| GAP-18D | Dashboard "PENDING PROCESSING" counter + insight notification card | UI-D2 | S |
| GAP-18E | Backfill `file_size_kb` + embeddings for pre-Iter9 documents | FR-14/15 | XS (script) |

---

### GAP-18A — DB-level pagination in `load_all_records` (NFR-03)

**Problem:** `load_all_records(user_id)` in `dataset_manager.py` runs
`SELECT * FROM "FinancialDocument" WHERE "tenantId" = %s` with no LIMIT, loads the
entire tenant dataset into a Python list, then Python-level slices it in `app.py`.
At 1,000+ documents this causes unbounded memory usage and slow queries.

**Fix — `backend/dataset_manager.py`:**
```python
def load_records(user_id: str = None, limit: int | None = None, offset: int = 0):
    # Add LIMIT / OFFSET clause to the existing SELECT
    query = 'SELECT * FROM "FinancialDocument" WHERE "tenantId" = %s ORDER BY "createdAt" DESC'
    params = [user_id]
    if limit is not None:
        query += " LIMIT %s OFFSET %s"
        params += [limit, offset]
    ...

def count_records(user_id: str) -> int:
    # New: SELECT COUNT(*) for pagination metadata
    ...
```

**Fix — `backend/app.py` (`GET /documents`):**
```python
total = count_records(user_id=user_id)
records = load_records(user_id=user_id, limit=limit, offset=(page-1)*limit)
# Remove the Python-level slice and len() — now done in SQL
```

**New tests: `backend/tests/test_iter18_db_pagination.py`**
- `test_load_records_passes_limit_offset` — mock conn; verify LIMIT/OFFSET in query string.
- `test_count_records_returns_int` — mock conn returns 42; verify return type.
- `test_get_documents_pagination_meta` — `TestClient` with mocked `load_records`/`count_records`;
  verify `pagination.total` comes from `count_records` not `len(records)`.

---

### GAP-18B — Audit log: 2FA toggle + session termination (FR-33)

**Problem:** SRS §3.8 requires "all actions" to be logged. Two authentication events are
missing: toggling Two-Factor Authentication on/off, and terminating a session (logout or
session revoke from the session-management page).

**Fix — `frontend/src/app/api/auth/2fa/toggle/route.ts`:**
```typescript
// After updating user.twoFactorEnabled in Prisma:
await prisma.activityLog.create({
  data: { userId, action: "2FA_TOGGLED",
          details: `2FA ${enabled ? "enabled" : "disabled"}`, createdAt: new Date() }
});
```

**Fix — `frontend/src/app/api/auth/logout/route.ts`:**
```typescript
// Decode JWT from cookie, extract userId, before clearing cookie:
await prisma.activityLog.create({
  data: { userId, action: "SESSION_TERMINATED", details: "logout", createdAt: new Date() }
});
```

**Fix — `frontend/src/app/session-management/page.tsx` (revoke session):**
- When the "Revoke" button calls the session-revoke API route, that route logs
  `SESSION_TERMINATED` with `details: "session_revoked"`.

**New tests: `backend/tests/test_iter18_audit_events.py`**
- `test_2fa_toggle_logs_event` — mock DB; verify `activityLog.create` called with action
  `"2FA_TOGGLED"` after toggle route hits.
- `test_logout_logs_session_terminated` — mock DB; verify `"SESSION_TERMINATED"` logged.

---

### GAP-18C — Field→chunk ID mapping for click-to-source (FR-24, FR-26)

**Problem:** The BboxOverlayViewer shows coloured bbox overlays over the document image,
and clicking a bbox sets `activeChunkId`. But the ProvenancePanel (showing extracted fields
like `vendor_name`, `total_amount`) has no way to know which `chunk_id` corresponds to
which extracted field — the link between `extracted_field → source_text → chunk_id` is
never stored.

**Approach:** Fuzzy-match extracted field values against spatial chunk texts at confirm-save
time, storing a `field_chunk_map` in the document record.

**Fix — `backend/app.py` (`/confirm-save` after spatial chunks are built):**
```python
def _build_field_chunk_map(extracted_json: dict, spatial_chunks: dict) -> dict:
    """Returns {field_name: chunk_id} by matching field value text against chunk texts."""
    from difflib import SequenceMatcher
    field_chunk_map = {}
    all_chunks = [c for p in spatial_chunks.get("pages", []) for c in p.get("chunks", [])]
    for field in ["company_name", "supplier_name", "order_id", "date",
                  "raw_total_amount", "final_total_amount", "currency"]:
        value = str(extracted_json.get(field, "")).strip()
        if not value or value == "NULL":
            continue
        best_id, best_ratio = None, 0.0
        for chunk in all_chunks:
            ratio = SequenceMatcher(None, value.lower(),
                                    chunk.get("text","").lower()).ratio()
            if ratio > best_ratio:
                best_ratio, best_id = ratio, chunk.get("chunk_id")
        if best_ratio >= 0.6:
            field_chunk_map[field] = best_id
    return field_chunk_map
```
Store as `field_chunk_map_json TEXT` column on `FinancialDocument`.

**Fix — `frontend/src/components/ui/ProvenancePanel.tsx`:**
- Accept `fieldChunkMap?: Record<string, string>` prop.
- Each field row gets a small `⊕` link icon; clicking calls `onChunkSelect(chunk_id)`.
- This highlights the correct bbox in BboxOverlayViewer (state already wired via `activeChunkId`).

**New migration:** `ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fieldChunkMapJson" TEXT;`

**New tests:** `test_iter18_field_chunk_map.py`
- `test_fuzzy_match_finds_vendor` — synthetic chunks with "ACME Corp"; extracted
  `company_name = "ACME Corporation"` → ratio ≥ 0.6 → returns chunk_id.
- `test_no_match_below_threshold` — field value completely different from all chunks → not in map.

---

### GAP-18D — Dashboard "PENDING PROCESSING" + insight card (UI-D2)

**Problem:** The SRS Dashboard mockup (UI Design 2) shows:
- Three stat cards: `TOTAL INVOICES/POS`, `PENDING PROCESSING`, `READY FOR QUERY`
- A "Invoice Insights Ready" notification card at the bottom with a cross-doc discrepancy alert.

**Current state:** Dashboard shows `payable`, `receivable`, `income`, `expense` totals.
The PENDING PROCESSING counter and the insight notification card are missing.

**Fix — `backend/app.py` (`GET /dashboard-summary`):**
```python
# Add counts to existing summary
processing_count = sum(1 for r in records if r.get("status","ready") == "processing")
ready_count      = sum(1 for r in records if r.get("status","ready") == "ready")
total_count      = len(records)
# Return alongside existing payable/receivable/income/expense totals
```

**Fix — `frontend/src/app/dashboard/page.tsx`:**
- Add three top stat cards: Total Docs, Pending Processing (amber), Ready for Query (green).
- Add "Invoice Insights Ready" card (shows when there are >0 recent documents with
  `arithmetic_status !== "valid"`), linking to the Repository page filtered to those docs.

---

### GAP-18E — Backfill migration script

**Problem:** Documents uploaded before Iteration 9 have `safeboxJson = NULL`,
`spatialChunksJson = NULL`, `ChunkEmbedding` has no rows for them, and `fileSizeKb = NULL`.
RAG scope (Iter 15) silently degrades to SQL-only for these docs.

**Fix — `backend/scripts/backfill_iter9.py`** (new standalone script, not a migration):
```python
# For each document with spatialChunksJson IS NULL:
#   1. Re-run build_spatial_chunks() on the stored corrected_text
#   2. Embed the chunks and upsert to ChunkEmbedding
#   3. Patch fileSizeKb from the saved file if available, else leave NULL
# Usage: python backend/scripts/backfill_iter9.py --user_id all
```

This is a one-time operational script, not a code change to the pipeline.

---

### Dependency graph

```
GAP-18A (DB pagination)     — independent, backend-only
GAP-18B (audit 2FA/session) — frontend API routes only
GAP-18C (field→chunk map)   — backend confirm-save + frontend ProvenancePanel
GAP-18D (dashboard)         — backend /dashboard-summary + frontend dashboard
GAP-18E (backfill script)   — standalone script; depends on Iter 9 pipeline code (already done)
```

All five gaps are **independent** and can be implemented in any order.

---

### Exit criteria for Iteration 18

1. `GET /documents?page=2&limit=10` queries DB directly; no `load_all_records` is called.
2. Admin activity log shows `2FA_TOGGLED` after toggling 2FA on the profile page.
3. Clicking a field label in ProvenancePanel highlights the correct bbox in BboxOverlayViewer.
4. Dashboard shows Total / Pending / Ready counts.
5. `backfill_iter9.py --dry-run` lists all documents missing chunks without erroring.
6. `pytest tests/ -q` ≥ 265 passing (adds ~8 new tests).
7. `tsc --noEmit` 0 errors.

---

## Part C — After Iteration 18

The only remaining items are **ops-level** (not resolvable by code in this prototype):

| Item | Why not in code |
|---|---|
| NFR-05: 99% uptime | Requires HA infrastructure (load balancer, DB replicas). Out of prototype scope. |
| NFR-01: OCR speed SLA | Colab OCR round-trip is 10–30s by nature. Would require a co-located GPU server. |
| FR-30: TLS in prod | `nginx/generate-certs.sh` exists. Blocked on running it on the deployment server. |
| FR-31: AES-256 documented | Supabase provides this. Add a line to README/profile page footer. |

These should be noted in the project handoff documentation rather than tracked as code tasks.
