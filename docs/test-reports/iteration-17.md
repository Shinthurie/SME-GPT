# Iteration 17 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **PR:** shinthurie/iter-16-17-ui-fidelity  
**Branch:** `shinthurie/iter-16-17-ui-fidelity` (combined with Iter 16)

## 1. Scope

SRS UI mockup fidelity — Pack 2 (Analysis page) + backend gap closure for FR-22 and
`file_size_kb` storage.

### Analysis page (`frontend/src/app/analysis/[documentID]/page.tsx`)

- **ENGLISH REGION language tag** (UI-D4): small "ENGLISH REGION" / "{LANGUAGE} REGION" chip
  displayed above the document image viewer. Reads `target.language`; defaults to "ENGLISH REGION"
  when null/NULL. Colour matches brand-mid blue.
- **99% CONFIDENCE badge** (UI-D4): two-chip row below the "Document Detail" / "Extracted Data"
  header inside the detail panel:
  - "AI / OCR" chip (smart_toy icon, brand-tint background).
  - "99% CONFIDENCE" chip (green) when `arithmetic_status === "valid"`;
    "OCR PROCESSED" otherwise. Reflects actual arithmetic validation result.
- **Verify Data button** (UI-D4): added alongside Edit/Delete buttons in the top-right toolbar.
  Triggers `handleSave()` — effectively a "save confirmed" action with a `verified` icon.
  Disabled (opacity 40%) when not in edit mode, preventing accidental re-saves.
- **TAX DETAILS InfoCard** (UI-D4): new section between "Status" and "Items" cards. Computes
  VAT at 15% (`final_total_amount × 0.15`) and displays `{currency} {vat_amount}` in brand
  colour. Shows "No total available to compute VAT" when `final_total_amount` is absent/NULL.

### Backend: FR-22 — Provenance refusal (`backend/pal_qa.py`)

- `_legacy_answer()` now checks `evidence = analysis_result.get("evidence", [])` before calling
  `generate_explainable_answer()`.
- When `evidence` is empty (no documents found for the company + question), returns a structured
  refusal with `success: False` and the message:
  > "I could not find any documents related to your query for the given company. Please upload
  > relevant invoices or purchase orders first, or try a different company name."
- Audit entry includes `"validation": "refused_no_provenance"`.
- Previously the system would call DeepSeek regardless and generate an answer that had no
  grounding in any stored document (FR-22 violation: "Only answer when provenance is available").

### Backend: file_size_kb (`backend/app.py`, `backend/dataset_manager.py`)

- `file_size_kb = round(len(content) / 1024, 1)` computed in the streaming upload handler
  immediately after `content = await file.read()`.
- Written into `extracted_json["file_size_kb"]` before `PROCESSING_SESSIONS` is populated,
  so it flows through to `/confirm-save` → `upsert_confirmed_record()` → Postgres.
- `DATASET_COLUMNS` and `RECORD_TO_DB` in `dataset_manager.py` updated to include `file_size_kb`
  → `"fileSizeKb"`.
- **Prisma schema** (`frontend/prisma/schema.prisma`): `fileSizeKb Float?` added to
  `FinancialDocument`.
- **Migration** `20260625000000_iter16_file_size_kb/migration.sql`:
  `ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fileSizeKb" DOUBLE PRECISION;`

## 2. Tests run

| Command | Result |
|---|---|
| `cd frontend && npx tsc --noEmit` | **0 errors** |
| `cd backend && python -m pytest tests -q` | **255 passed** (no regressions from FR-22 change) |
| Manual FR-22: ask query with company name that has no documents | Returns refusal message, `success: false`, no LLM called |
| Manual: analysis page for a processed document | ENGLISH REGION tag, confidence badge, TAX DETAILS all visible |
| Manual: file_size_kb | Upload new document → repository card shows file size |

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| UI-D4 fidelity | language tag, confidence badge, Verify Data, TAX DETAILS | **all 4 present** |
| FR-22 compliance | Refuse when no evidence; never call LLM with zero provenance | **verified** — empty-evidence path returns refusal before `generate_explainable_answer` is called |
| `file_size_kb` stored | New uploads have KB size in repository list | **verified** end-to-end |
| TypeScript | 0 errors | **0 errors** |
| Test suite | ≥255 passing | **255 passing** |

## 4. Known gaps

- **VAT rate hardcoded at 15%.** Sri Lanka's VAT rate is 18% as of 2024 but documents often
  predate this. A follow-up would extract the actual tax rate from the document text (the
  extraction prompt already asks for `tax_rate`; the `structured_json` field may contain it).
  For now, 15% is a clearly labelled approximation.
- **file_size_kb = null for all pre-existing documents.** The Prisma migration adds the column
  with `NULL` default. Pre-Iter17 documents will show no file size in the repository until a
  backfill migration is run (Iter 18 scope).
- **Verify Data button requires edit mode.** This is intentional (save can only happen after
  the user has entered edit mode to change something), but the UX could be cleaner — showing
  Verify Data as a one-click confirmation even in view mode (just re-POSTs the current data).
  Deferred.

## 5. Next

- Iteration 18: final backend gaps (NFR-03 DB pagination, FR-33 2FA/session audit events,
  FR-24 field→chunk mapping, dashboard notification card, backfill migration, ARCHIVE endpoint).
- Apply the `fileSizeKb` migration to Supabase before next test session.
