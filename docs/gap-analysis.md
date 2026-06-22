# SME-GPT — Gap Analysis (SRS v1.2 traceability)

Maps every SRS requirement to its current status and the iteration that delivers it.
Update this file as iterations land. Status: ❌ none · 🟡 partial · ✅ done.

## Functional Requirements

| FR | Requirement | Status | Where / Plan |
|---|---|---|---|
| FR-01 | Accept PDFs and images (JPG/PNG) | 🟡 | `app.py` upload; harden in Iter 0/1 |
| FR-02 | Convert PDF pages to 300 DPI images | 🟡 | `document_pipeline.py` (pdf2image); standardize DPI Iter 2 |
| FR-03 | Preprocess (deskew, denoise, crop) | 🟡 | partial in pipeline; formalize Iter 2 |
| FR-04 | Reject corrupted/unreadable docs with clear error | 🟡 | improve error contract Iter 1 |
| FR-05 | Extract text in Sinhala & English | ✅ | Surya OCR (colab/local) |
| FR-06 | Bounding boxes for every text segment | 🟡 | canonical box schema + safeguard in `ocr_correction.py` (Iter 2); not yet wired into live pipeline/DB |
| FR-07 | Store OCR confidence levels | 🟡 | carried in canonical box schema (Iter 2); not yet persisted to DB |
| FR-08 | Pluggable OCR engines | 🟡 | `OCRService` interface + `MockSuryaOCRService` (Iter 2, `backend/ocr_service.py`); real Surya v2 engine blocked on vllm/llama.cpp backend; v1 colab/local still serves live app |
| FR-09 | Detect document structure (tables/headers/blocks) | 🟡 | `backend/spatial_serialization.py` row clustering + header detection (Iter 3); not yet wired into live pipeline |
| FR-10 | Extract key fields (vendor, invoice no, dates, totals) | 🟡 | `ocr_to_json_extractor.py` (live); C2 KeyValue chunks + canonical-field mapping built standalone (Iter 3), align/replace in Iter 5 |
| FR-11 | Extract line-item tables (rows/cols) | 🟡 | extractor (live); C2 `line_item_row`/`line_item_block` templates built standalone (Iter 3) |
| FR-12 | Multi-page extraction | 🟡 | pipeline handles pages; `build_spatial_chunks` iterates pages (Iter 3); multi-table-per-page clustering is a follow-up |
| FR-13 | Store page + bbox per extracted field | 🟡 | C2 provenance (`page`, `bbox`, `token_bboxes`) built in `spatial_chunks.json` (Iter 3); not yet persisted to DB |
| FR-14 | Convert extracted content to embeddings | ❌ | Iter 4 (pgvector) |
| FR-15 | Store embeddings in a vector DB | ❌ | Iter 4 (pgvector) |
| FR-16 | Semantic retrieval for queries | ❌ | Iter 4 |
| FR-17 | Return provenance metadata with results | ❌ | Iter 4 |
| FR-18 | Natural-language questions (si/en) | 🟡 | `ai_helper.py`; PAL in Iter 5 |
| FR-19 | RAG pipeline to retrieve context before answering | ❌ | Iter 4–5 |
| FR-20 | Calculator/deterministic arithmetic | 🟡 | `arithmetic_validator.py`; PAL executor Iter 5 |
| FR-21 | Multi-document reasoning (sum across invoices) | 🟡 | `data_tools.py` over CSV; PAL + C4 Iter 5–6 |
| FR-22 | Only answer when provenance available | ❌ | Iter 5 (citations) |
| FR-23 | Store full provenance (bbox, page, raw text, model version) | ❌ | Iter 1 (schema) + Iter 2–3 |
| FR-24 | Highlight exact source text in UI | ❌ | Iter 7 |
| FR-25 | Show derivation steps for aggregated answers | ❌ | Iter 5 (audit) + Iter 7 (UI) |
| FR-26 | Click values to see origin | ❌ | Iter 7 |
| FR-27 | Document viewer with overlays | ❌ | Iter 7 |
| FR-28 | Bilingual UI (si/en) | ✅ | i18n in `frontend/src/lib` |
| FR-29 | Clear errors and status updates | 🟡 | improve Iter 7 |
| FR-30 | TLS for all communication | 🟡 | deploy concern; Iter 8 |
| FR-31 | Encrypt stored data (AES-256) | ❌ | Supabase at-rest; Iter 8 |
| FR-32 | Role-Based Access Control | ❌ | Iter 8 |
| FR-33 | Audit logs for all actions | 🟡 | `ActivityLog` exists; extend Iter 8 |

## Non-Functional Requirements

| NFR | Requirement | Status | Plan |
|---|---|---|---|
| NFR-01 | OCR processes pages within seconds | 🟡 | depends on Surya; measure Iter 2 |
| NFR-02 | Fast query responses | 🟡 | measure after Iter 5 |
| NFR-03 | Handle large document volumes | ❌ | Postgres + indexes Iter 1 |
| NFR-04 | Auto-retry on OCR/layout errors | 🟡 | colab→local fallback exists; formalize |
| NFR-05 | 99% uptime | ❌ | deploy/ops Iter 8 |
| NFR-06 | Simple, intuitive UI | 🟡 | ongoing |
| NFR-07 | Bilingual UI | ✅ | done |
| NFR-08 | Installable on mobile + desktop | ❌ | PWA later |
| NFR-09 | Responsive UI | 🟡 | ongoing |
| NFR-10 | Modular system | 🟡 | improves each iteration |
| NFR-11 | Easy to update/replace models | 🟡 | `OCRService` + LLM abstraction Iter 2/5 |
| NFR-12 | Run on different devices | 🟡 | Docker Iter 8 |
| NFR-13 | Docker containers | ❌ | Iter 8 |
| NFR-14 | GDPR-like data handling | ❌ | Iter 8 |
| NFR-15 | Audit logs permanent for 1 year + tenant isolation | 🟡 | tenancy Iter 1, retention Iter 8 |

## Research components coverage

| Component | Status | Iteration |
|---|---|---|
| C1 — Semantic OCR Post-Correction | 🟡 (box-level + numeric safeguard built & tested against a mock v2 fixture; not wired into the live pipeline; real OCR engine pending vllm/llama.cpp) | Iter 2 |
| C2 — Layout-Aware Spatial Serialization | 🟡 (row clustering, header detection, x-axis binding, template serialization, `spatial_chunks.json` built & tested against the same mock fixture; not wired into the live pipeline) | Iter 3 |
| C3 — Neuro-Symbolic PAL Arithmetic QA | 🟡 (ad-hoc) | Iter 5 |
| C4 — Multi-Tenant Relationship Index | ❌ | Iter 6 (tables Iter 1) |
