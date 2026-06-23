# Iteration 16 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **PR:** shinthurie/iter-16-17-ui-fidelity  
**Branch:** `shinthurie/iter-16-17-ui-fidelity` (combined with Iter 17)

## 1. Scope

SRS UI mockup fidelity — Pack 1. Brings four frontend pages to match the UI Design 3–6
mockups in SRS §4.1. Frontend-only: no backend or schema changes in this iteration.

### Upload page (`frontend/src/app/upload/page.tsx`)

- **OCR Language Engine toggle** (UI-D3): EN / Sinhala pill buttons above the drop zone.
  Tracks `ocrLang: "en" | "si"` state and appends `ocr_language` to the `FormData` sent
  to `/process-document-stream`. Backend receives it as an extra form field (Surya is
  bilingual by default; the hint is stored for future single-language tuning).
- **AES-256 security banner** (UI-D3): shield icon + "Enterprise Security: All data is
  processed using AES-256 encryption…" text block, displayed below the pipeline steps.
- **"Begin Extraction" button** (UI-D3): renamed from "Start Processing" / "Processing Done ✓"
  to "Begin Extraction" / "Extraction Done ✓" to match the SRS mockup label exactly.

### Repository page (`frontend/src/app/repository/page.tsx`)

- **Search bar** (UI-D7): magnifying-glass icon + text input above the type-filter tabs.
  Client-side filter across `document_id`, `company_name`, `supplier_name` with a clear (✕)
  button. Added `searchQuery` state; `filtered` useMemo now applies both tab filter and search.
- **Dynamic status badge** (UI-D7): was hardcoded `"ready"`. Now uses `statusBadge(item.status)`
  helper: PROCESSING (orange), ERROR (red), READY (green).
- **File size display** (UI-D7): `file_size_kb` added to `RepoDocument` type; `formatFileSize()`
  helper renders "245 KB" / "1.2 MB". Shows when non-null; existing documents show nothing
  (backend populates this for new uploads — see Iter 17).
- **ARCHIVE action** (UI-D7): per-card ARCHIVE button. Clicking toggles an inline information
  panel explaining the feature is coming soon. Full archive endpoint is in Iter 18 scope.
- **REFRESH LIST button** (UI-D7): bottom-of-list button that calls `loadDocuments()` again.
  `loadDocuments` extracted from the `useEffect` into a named function to enable this reuse.

### Query page (`frontend/src/app/query/page.tsx`)

- **DOCUMENT AI chip** (UI-D5): pill badge in the top-right bar beside the language switcher.
- **Input action icons** (UI-D5): attach_file / mic / g_translate icons in the textarea footer
  (left side). Non-functional (no file attachment or mic API wired) but visually match the SRS.
- **Auto-Detection active indicator** (UI-D5): right side of the textarea footer; radio_button
  icon + "Auto-Detection active" text in brand-mid colour.
- **OCR / NLP / XAI pipeline tabs** (UI-D5): three icon tiles below the Process Query button.
  Static, visual-only — shows the three AI layers the system uses (document_scanner → psychology
  → explain). Labels "OCR", "NLP", "XAI".

### Answer page (`frontend/src/app/answer/page.tsx`)

- **Header rename + accuracy badge** (UI-D6): "Query Result" → "AI Business Insight" with
  "98% Accuracy" badge on the right. Sub-label "Insights & Analysis".
- **4 action buttons** (UI-D6): rendered as a 2×2 (mobile) / 4-col (desktop) grid below the
  answer card:
  - **Adjust Total**: navigates to the first evidence document's analysis page.
  - **Notify Supplier**: toggles an inline "compose message" information panel.
  - **Export**: downloads `query-result-{timestamp}.json` via `Blob` + object URL.
  - **Flag for Review**: toggles a red "Flagged ✓" state on the button (persisted in
    component state; no backend persistence needed for a prototype flag).
- **GO TO PO deep link** (UI-D6): inside each evidence card, a "GO TO PO →" button appears
  when `item.document_type === "po"`. Navigates to `/analysis/{document_id}`.
- **ROW citations** (UI-D6): each line item in the evidence card now shows a "ROW N" chip
  (N = 1-based index) matching the "ROW 12" / "LINE 4" citations in the SRS mockup.

## 2. Tests run

| Command | Result |
|---|---|
| `cd frontend && npx tsc --noEmit` | **0 errors** |
| Manual: Upload page visible in browser | OCR toggle, security banner, "Begin Extraction" confirmed |
| Manual: Repository search bar filters correctly | Typing "AIESEC" shows only AIESEC documents |
| Manual: Answer page EXPORT button | Downloads valid JSON file of the query result |

No backend changes → backend test suite unchanged (255 passing from Iter 15).

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| UI-D3 fidelity | OCR toggle, security banner, button label | **all 3 present** |
| UI-D5 fidelity | icons, auto-detect, tabs | **all present** |
| UI-D6 fidelity | accuracy badge, 4 buttons, GO TO PO, row cites | **all present** |
| UI-D7 fidelity | search, status, archive, refresh, file size | **all present** |
| TypeScript | 0 errors | **0 errors** |

## 4. Known gaps

- **No backend-stored "flagged" state.** The FLAG FOR REVIEW button toggles local React state
  only. A proper flag would need a DB column or a separate `FlaggedQuery` table — deferred to
  Iter 18 if needed.
- **Notify Supplier** is purely informational (no email API). SRS doesn't specify the backend
  for this feature; the UI panel is the designed deliverable.
- **ARCHIVE endpoint** not yet implemented. The ARCHIVE button shows an info panel. Backend
  endpoint + DB `archivedAt` field in Iter 18.
- **File size** shows for new uploads only. Pre-existing documents have `file_size_kb = null`
  until a backfill migration is run (Iter 18).

## 5. Next

- Iteration 17: Analysis page fidelity (ENGLISH REGION, confidence badge, Verify Data, TAX
  DETAILS) + backend FR-22 (provenance refusal) + `file_size_kb` storage.
