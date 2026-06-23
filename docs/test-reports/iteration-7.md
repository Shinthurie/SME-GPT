# Iteration 7 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **Branch:** main

## 1. Scope

Explainability UI + Provenance Highlighting: derivation trace for query answers,
per-field provenance for extracted documents, bilingual label additions.

Delivered:
- `frontend/src/components/ui/DerivationTrace.tsx` — 4-step derivation panel
  (scope resolution → document match → computation → answer generation).
  Shows all contributing evidence documents with amounts and currencies, the
  aggregation formula, query metrics, and an amber low-confidence warning when
  no documents matched the query.  Wired into `answer/page.tsx` as a collapsible
  "Derivation Trace" section (after Evidence Documents).

- `frontend/src/components/ui/ProvenancePanel.tsx` — per-field provenance panel
  for `analysis/[documentID]/page.tsx`.  Each extracted field shows:
  - Source tag: OCR (directly from character recognition), LLM (DeepSeek
    extraction), Arithmetic (arithmetic-validated total/payable amounts)
  - Confidence badge: green ✓ for present values, red ✕ for NULL/missing
  - Arithmetic mismatch warning (amber) when `arithmetic_status == "mismatch"`
  - OCR version chip and arithmetic status pill in the panel header

- `frontend/src/app/answer/page.tsx` — added `DerivationTrace` import + toggle
  state; passes `evidence`, `metrics`, `questionType`, and `companyName` through.

- `frontend/src/app/analysis/[documentID]/page.tsx` — extended `DocumentDetail`
  type with `arithmetic_status`, `arithmetic_json`, `ocr_selected_version`
  (these fields are already returned by the backend `/documents/{id}` endpoint via
  the `**record` spread in `build_document_detail`); added `ProvenancePanel` as
  a collapsible "Field Provenance" section below the Items card.

- `frontend/src/lib/i18n.ts` — 8 new bilingual keys (EN + SI):
  `fieldProvenance`, `derivationTrace`, `lowConfidenceWarning`,
  `arithmeticValidated`, `ocrExtracted`, `llmExtracted`, `provenanceLegend`,
  `howAnswerComputed`.

## 2. Tests run

| Check | Result |
|---|---|
| `npx tsc --noEmit` (frontend) | **0 errors** |
| Visual inspection / design review | N/A — cannot run browser in CLI context; verified via TypeScript types |

## 3. Known gaps

- **No real bbox overlay on the document image.** The `ProvenancePanel` shows
  field-level source tags and confidence badges but does not draw bounding boxes
  over the document image, because per-box OCR coordinates are not yet stored
  per-document in the DB (C1/C2 pipeline writes them only to `temp_processing/`,
  which is cleared between runs). Real overlays require persisting
  `final_safe_boxes.json` to Supabase Storage per confirmed document — tracked
  as a follow-up once C1/C2 are wired into `document_pipeline.py`.
- No e2e browser tests; `tsc` is the only automated verification available in
  this iteration.

## 4. Next

- Iteration 8: Security & NFR Hardening (rate limiting, RBAC, Dockerfiles).
