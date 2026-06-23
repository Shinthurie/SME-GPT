# SME-GPT — Development Roadmap

This roadmap turns SME-GPT from a CSV-backed prototype into a professional, well-tested system
that realizes the 4 research components and the SRS (v1.2) requirements. We build **incrementally**,
shipping one iteration at a time, and **every iteration ends with tests + a test report + a reviewed PR**.

> Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Iteration 0 — Professionalization & Foundation (shared)

Goal: a clean, collaborative repo with CI, docs, and the Supabase backend provisioned.

- [~] Documentation set under `docs/` (this file, ARCHITECTURE, WORK_DIVISION, CONTRIBUTING, TESTING, gap-analysis, component specs)
- [ ] Root `README.md` rewrite (professional overview + setup)
- [ ] `.env.example` for backend and frontend (no secrets committed)
- [ ] `.github/` PR template + issue templates + CI workflow (`pytest`/`ruff` backend, `eslint`/`tsc`/`build` frontend)
- [ ] Linters/formatters: `ruff` + `black` (backend), `eslint` + `prettier` (frontend)
- [ ] pytest harness + test DB config
- [ ] Supabase project provisioned: Postgres + `pgvector` extension + Storage bucket
- [ ] GitHub: protect `main`, create Project board, seed issues per iteration
- [ ] **Exit criteria:** green CI on a trivial PR; both members can clone + run locally

## Iteration 1 — Data Layer: CSV → Supabase Postgres + tenancy

Goal: replace the CSV with a real, tenant-isolated relational schema.

- [x] Schema: `FinancialDocument`, `LineItem`, `query_history` (Supabase Postgres; pgvector enabled)
- [x] C4 tables added now (used later): `Entity`, `EntityAlias`, `DocLink` (research §6)
- [x] `tenant_id` (= user id) on every table; enforced on all reads/writes
- [x] Replace `backend/dataset_manager.py` CSV logic with DB access layer (`db.py` + psycopg)
- [x] Migration script: `financial_documents_clean.csv` → Postgres (`migrate_csv_to_db.py`, idempotent/dry-run)
- [x] **Tests:** CRUD round-trip + tenant isolation — 6 passing vs Supabase
- [ ] _Follow-up:_ user imports legacy rows (`--tenant`) + end-to-end app smoke after re-login

## Iteration 2 — Component 1: Semantic OCR Post-Correction

Goal: box-level correction with numeric immutability (DeepSeek instead of fine-tuned Gemma).

- [x] Refactor `llm_correction.py` to operate per OCR box (`correct_box`, `correct_boxes_for_page`)
- [x] Output `final_safe_boxes.json` (`text, bbox, confidence, locked_digits, source`)
- [x] Formalize `safe_correct()` numeric safeguard (reject if digit sequence changes — research §9.2)
- [x] Wrap Surya (colab/local) behind a pluggable `OCRService` interface (FR-08); keep standalone
- [x] Quality report scaffolding (`compute_cer`, `compute_nar` in `llm_correction.py`)
- [x] **Tests:** 33 numeric-safeguard unit tests passing (pure Python, no DB/LLM/OCR needed)

## Iteration 3 — Component 2: Layout-Aware Spatial Serialization

Goal: deterministic `spatial_chunks.json` with provenance.

- [x] Row clustering (y-axis, dynamic threshold) — `cluster_rows_by_y`
- [x] Header detection (English + Sinhala keywords) — `is_header_row`
- [x] Header→row binding (x-axis nearest-center) — `bind_to_nearest_header`
- [x] Template-based serialization (Header / KeyValue / LineItem / Text) — `classify_row`
- [x] Emit `spatial_chunks.json` schema (chunk_id, type, page, bbox, text, token_ids, header_ref)
- [x] `document_pipeline.py` writes `temp_processing/spatial_chunks.json` per document
- [x] **Tests:** 36 unit tests covering clustering, header detection, classification, binding, schema, multi-page provenance

## Iteration 4 — Indexing & Vector Retrieval (RAG)

Goal: semantic retrieval over chunks with provenance.

- [ ] Embed `SpatialChunk.text` into pgvector; metadata = tenant/doc/chunk/bbox
- [ ] Retrieval API (top-k + provenance) (FR-14…17)
- [ ] **Tests:** retrieval hit-rate harness on labelled queries

## Iteration 5 — Component 3: Neuro-Symbolic PAL Arithmetic QA

Goal: hallucination-free financial answers.

- [ ] DeepSeek planner → strict JSON plan
- [ ] Plan validator (allow-list: tasks, operators, canonical fields)
- [ ] Deterministic pandas executor
- [ ] Language-aware answer generator (si/en) + citations (bbox)
- [ ] Retry loop (×2) + clarification + scope resolver
- [ ] Replace ad-hoc logic in `ai_helper.py` / `data_tools.py`
- [ ] **Tests:** arithmetic-accuracy harness vs ground truth (target ~100% on supported ops)

## Iteration 6 — Component 4: Multi-Tenant Relationship Index

Goal: cross-document retrieval via entities + links.

- [ ] Normalization (vendor/ref) + conservative fuzzy aliasing (research §7)
- [ ] Edge creation with evidence JSON (page/bbox/chunk_id)
- [ ] Query-time APIs: `expand_related_docs`, `filter_docs`
- [ ] Wire into C3 scope resolver
- [ ] **Tests:** cross-document recall on linked queries (e.g. "Did we pay for PO-101?")

## Iteration 7 — Explainability UI + Provenance Highlighting

Goal: users can verify "where the answer came from."

- [ ] Document viewer with bbox overlays
- [ ] Click-to-source on extracted fields and answers
- [ ] Derivation trace for aggregated answers
- [ ] Low-confidence warnings; bilingual toggle polish (FR-23…29)
- [ ] **Tests:** component + e2e UI tests

## Iteration 8 — Security & NFR Hardening + Deployment

Goal: production-grade posture.

- [ ] RBAC roles (admin / accountant / owner / auditor) (FR-32)
- [ ] Audit logs for sensitive actions (FR-33), 1-year retention (NFR-15)
- [ ] TLS, encryption-at-rest (Supabase), secure password hashing
- [ ] Dockerfiles + `docker-compose`; rate limiting
- [ ] **Tests:** authz tests, smoke deploy

---

## Working agreement (applies to every iteration)

1. Branch from `main` (`feat/*`, `fix/*`, `docs/*`).
2. Write code + tests together.
3. Run tests locally; write `docs/test-reports/iteration-N.md`.
4. Tick the boxes above; update `docs/gap-analysis.md`.
5. Open a PR; the other member reviews; merge only on green CI.
