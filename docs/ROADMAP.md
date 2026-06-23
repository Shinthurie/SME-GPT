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

- [x] Box-level correction module added (`backend/ocr_correction.py`, `correct_box`/`correct_pages`)
      alongside (not replacing) the live whole-text `llm_correction.py` path
- [x] Output `final_safe_boxes.json` (`text, bbox, confidence, locked_digits, source`)
- [x] Formalize `safe_correct()` numeric safeguard (digit count + sequence + decimal structure)
- [x] Wrap Surya behind a pluggable `OCRService` interface (FR-08) — `backend/ocr_service.py`,
      canonical box schema, `MockSuryaOCRService` (Surya v2-shaped fixture; real v2 blocked on
      a vllm/llama.cpp backend, see `docs/components/component-1.md`)
- [x] Quality report scaffolding (CER, NAR) — `build_quality_report()`; NAR=1.0 by construction,
      CER pending a ground-truth transcript fixture
- [x] **Tests:** 16 numeric-safeguard/adapter/pipeline unit tests, all passing
- [ ] _Follow-up:_ wire C1 into `document_pipeline.py` once C2 (layout) can consume boxes —
      extraction today expects a single page text blob, not per-box output
- [ ] _Follow-up:_ real `SuryaV2OCRService` once a vllm/llama.cpp inference backend is runnable
- [ ] _Follow-up:_ ground-truth transcript fixture for CER measurement

## Iteration 3 — Component 2: Layout-Aware Spatial Serialization

Goal: deterministic `spatial_chunks.json` with provenance.

- [x] Row clustering (y-axis, dynamic threshold) — `backend/spatial_serialization.py::cluster_rows`
- [x] Header detection (English + Sinhala keywords) — `detect_header_row`
- [x] Header→row binding (x-axis nearest-center) — `bind_row_to_headers`
- [x] Template-based serialization (LineItem / KeyValue / Header / section_text) — no free text
- [x] Emit `spatial_chunks.json` exact schema (research §9) with page+bbox+token_ids —
      `build_spatial_chunks`
- [x] **Tests:** 21 unit/end-to-end tests — clustering, header detection, x-axis binding,
      KeyValue classification, chunking-strategy thresholds, schema validation, never-drop-tokens,
      cell-extraction accuracy against `backend/sample_docs/invoice_mock_surya_v2.json`
- [x] _Side change:_ `ocr_service.py`'s `Table` blocks now expand to per-cell canonical boxes
      (`table_block_to_cell_boxes`) instead of one flattened text blob — C2's row-clustering
      algorithm needs per-cell geometry, which Surya v2's block-level bbox alone doesn't provide
- [ ] _Follow-up:_ multi-table-per-page handling — row clustering currently spans the whole page;
      two tables sharing the same y-range would need per-`table_id` clustering first
- [ ] _Follow-up:_ wire C1+C2 into `document_pipeline.py` once a real OCR engine is available
      (still mock-fixture-only; see Iteration 2's follow-ups)

## Iteration 4 — Indexing & Vector Retrieval (RAG)

Goal: semantic retrieval over chunks with provenance.

- [x] Embed `SpatialChunk.text` into pgvector; metadata = tenant/doc/chunk/bbox —
      `backend/vector_index.py` + `ChunkEmbedding` table (`docs/design/iter-4-schema.md`, applied)
- [x] Retrieval API (top-k + provenance) (FR-14…17) — `vector_index.retrieve_top_k()`
      (pgvector cosine distance, tenant-filtered, optional document scope)
- [x] **Tests:** 12 tests — hashing-embedding determinism, chunk flattening, in-memory ranking,
      a 5-query retrieval-hit-rate harness (100% on the mock fixture) vs. a naive whole-document
      baseline, and a live Supabase round-trip with tenant isolation
- [x] _Decision:_ DeepSeek has no embeddings endpoint, so embeddings use a separate
      `EmbeddingService` (mirrors `OCRService`): `intfloat/multilingual-e5-small` (local,
      CPU-friendly, mC4-trained so it covers Sinhala) is the real default; tests use a
      deterministic hashing embedding so the suite stays hermetic — same reasoning as
      monkeypatching DeepSeek in the C1 tests
- [ ] _Follow-up:_ `LocalMultilingualEmbeddingService` is untested in CI (model download/network) —
      same status as C1's real Surya v2 engine; verify it manually once dependencies are installed
- [ ] _Follow-up:_ wire retrieval into a FastAPI endpoint / C3 once C1+C2 are wired into
      `document_pipeline.py` and there's a real document to retrieve from

## Iteration 5 — Component 3: Neuro-Symbolic PAL Arithmetic QA

Goal: hallucination-free financial answers.

- [x] DeepSeek planner → strict JSON plan — `backend/pal_planner.py`
- [x] Plan validator (allow-list: tasks, operators, canonical fields) — `backend/pal_validator.py`
      (canonical fields = component-3.md's 10 + a documented `flow_type` extension —
      payable/receivable/income/expense is core to every query this app answers and there's no
      other canonical field for it; company-level scoping happens before the plan runs)
- [x] Deterministic pandas executor — `backend/pal_executor.py` (filters: eq/in/contains/gte/lte/
      between; aggregations: sum/avg/count/max/min; tasks: aggregate_sum/avg/count, compare,
      lookup_value, group_by_sum; mixed-currency aggregates auto-split into a per-currency
      breakdown instead of summing across currencies)
- [x] Language-aware answer generator (si/en) — `backend/pal_answer.py` (Sinhala/English
      auto-detected from the question); citations are `[]` for now — bbox citations need C1/C2
      wired into the live pipeline first, tracked as a follow-up
- [x] Retry loop (×2) + scope resolver — `backend/pal_qa.py` orchestrator + `backend/pal_scope.py`
      (tenant + company-name scoping over live `FinancialDocument`/`LineItem`; no C4 graph
      expansion yet, that's Iteration 6)
- [x] **Wired live into `/ask-query`** (`app.py`) — replaces the `ai_helper.py`/`data_tools.py`
      call site. PAL degrades to the pre-PAL ad-hoc logic (kept, not deleted) when DeepSeek can't
      produce a valid plan within the retry budget, the question is a listing intent PAL doesn't
      cover (e.g. "list my invoices"), or the validated plan matches zero rows — same
      "deterministic fallback when the LLM can't be trusted" philosophy as `safe_correct()`
- [x] **Tests:** 43 tests — validator allow-list, executor (all tasks/ops/aggs, mixed currency,
      empty input), scope row-flattening, planner/answer-generator DeepSeek boundaries
      (monkeypatched), and the full orchestrator including both fallback paths
- [ ] _Follow-up:_ "no rows retrieved" degrades straight to the legacy path instead of broadening
      the retrieval (component-3.md's literal failure-table behavior); simplification for this
      iteration, tracked for revisit
- [ ] _Follow-up:_ swap `pal_scope.py`'s row source for C2 SpatialChunks + vector retrieval
      (Iter 3/4) once C1/C2 are wired into `document_pipeline.py` — the planner/validator/executor
      are retrieval-source-agnostic, so this is a contained change
- [ ] _Follow-up:_ citations (bbox) once C1/C2 are wired in
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
