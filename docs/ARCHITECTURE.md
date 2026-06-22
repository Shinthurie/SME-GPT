# SME-GPT — Architecture

This document describes the **target architecture** (where we are heading) and notes which parts
exist today. We move toward it incrementally (see [ROADMAP.md](ROADMAP.md)).

---

## 1. High-level data flow

```
                      ┌──────────────────────────────────────────────────────────┐
  INGESTION (offline) │                                                          │
                      ▼                                                          │
  Upload (PDF/img) → Preprocess (300 DPI, deskew/denoise)                       │
        → OCR Service  [Surya: Colab remote → local fallback]  ← STANDALONE     │
        → C1 Semantic OCR Post-Correction (DeepSeek + numeric safeguard)        │
              → final_safe_boxes.json                                           │
        → C2 Layout-Aware Spatial Serialization (row cluster→header bind→tmpl)  │
              → spatial_chunks.json                                             │
        → C4 ingest: relationship index (entities / aliases / doc_links)        │
        → Vector indexing: embed chunk.text → pgvector (+ metadata, bbox)       │
                                                                                │
  QUERY (online)                                                                │
  User question (si/en)                                                         │
        → C4 Scope Resolver (SQL date filter + graph expansion)                 │
        → Vector Retrieval (top-k chunks + provenance)                          │
        → C3 PAL: Planner(LLM)→Validator→Deterministic Executor→Answer(LLM)     │
        → Answer + computed value + citations(bbox) + audit                     │
                                                                                │
  FRONTEND                                                                       │
  Document viewer w/ bbox overlays · click-to-source · derivation trace ────────┘
```

---

## 2. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn | existing |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind 4 | existing |
| Database | **Supabase Postgres** | replaces the CSV store |
| Vector store | **pgvector** (in Supabase) | one DB for relational + vectors |
| File storage | **Supabase Storage** | original + processed page images |
| LLM | **DeepSeek API** | substitutes fine-tuned Gemma (C1) + planner/answer (C3) |
| OCR | **Surya** (Colab remote / local) | standalone, pluggable behind `OCRService` |
| PDF→image | pdf2image + Poppler | existing |
| Auth | JWT + bcrypt (+ optional 2FA, device trust) | existing; RBAC added in Iter 8 |
| Deploy | Docker + compose | Iter 8 |

### Substitutions vs the research docs
- **C1 model:** research recommends a QLoRA-fine-tuned Gemma-2-2B. **We use DeepSeek API for now**
  (the numeric-safeguard logic is identical and model-agnostic; the model can be swapped later).
- **OCR:** Surya has known issues; it stays **standalone and pluggable** so the rest of the pipeline
  is never blocked on it. The `OCRService` interface lets us swap engines (FR-08).

---

## 3. Multi-tenancy

User-as-tenant for now: `tenant_id == user.id`. Every table carries `tenant_id` and every query
filters on it (research C4 requires strict tenant isolation; SRS NFR-15 requires tenant isolation).
Upgrading to organizations/teams later is a migration, not a redesign.

---

## 4. Canonical artifacts (the contracts between components)

These JSON shapes are the stable interfaces; components are decoupled through them.

### `final_safe_boxes.json` (C1 → C2)
```json
{ "page": 1, "boxes": [
  { "text": "...", "bbox": [x1,y1,x2,y2], "confidence": 0.71,
    "locked_digits": false, "source": "ai_corrected|raw_ocr" } ] }
```

### `spatial_chunks.json` (C2 → vector index / C3 / C4)
Top-level `{tenant_id, document_id, version, language_hint, pages:[{page, chunks:[SpatialChunk]}]}`.
`SpatialChunk` (required: `chunk_id, chunk_type, text, provenance.page, provenance.bbox,
metadata.source_component`). `chunk_type ∈ {line_item_row, line_item_block, key_value, header, section_text}`.
Full schema: [components/component-2.md](components/component-2.md).

### PAL plan (C3 internal)
```json
{ "task": "aggregate_sum", "scope": {"doc_ids": [...]},
  "filters": [{"field":"doc_date","op":"between","value":["2025-01-01","2025-01-31"]}],
  "measure": {"field":"total","agg":"sum"}, "group_by": [], "output": {"format":"currency"} }
```
Canonical fields: `item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor`.

### Relationship index (C4, persisted in Postgres)
`entities`, `entity_aliases`, `doc_links` (with `evidence JSONB`). Schema: [components/component-4.md](components/component-4.md).

---

## 5. Current state vs target (summary)

| Capability | Today | Target |
|---|---|---|
| Storage | CSV via pandas (`dataset_manager.py`) | Supabase Postgres + pgvector |
| OCR | Surya colab/local, text-level | same engines, box-aligned via `OCRService` |
| Correction | `llm_correction.py`, text blobs, token masking | C1 box-level + `safe_correct()` |
| Layout/serialization | none | C2 spatial chunks |
| Retrieval | none (heuristic SQL-ish over CSV) | vector RAG over chunks |
| Q&A | `ai_helper.py` freeform + `data_tools.py` | C3 PAL plan→validate→execute |
| Cross-doc linking | none | C4 relationship index |
| Provenance in UI | partial | bbox overlays + derivation trace |
| Tenancy / RBAC | user_id only, no roles | tenant_id everywhere + RBAC |

See [gap-analysis.md](gap-analysis.md) for the full FR/NFR traceability matrix.

---

## 6. Repository layout (target)

```
SME-GPT/
├── backend/         # FastAPI, AI/ML pipeline (C1–C4), tests
├── frontend/        # Next.js app, DB schema/migrations, UX
├── docs/            # all documentation (this folder)
│   ├── components/  # per-component specs
│   └── test-reports/# per-iteration results
├── .github/         # CI, PR/issue templates
├── API_CONTRACT.md  # backend↔frontend contract
└── surya_ocr_colab.ipynb
```
