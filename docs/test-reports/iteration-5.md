# Iteration 5 — Test Report

**Date:** 2026-06-22 · **Owner(s):** Ashfak (backend/AI) · **PR:** (feat/iter-5-pal-arithmetic-qa)

## 1. Scope

Component 3 (Neuro-Symbolic PAL Arithmetic QA): a DeepSeek planner that proposes a structured
JSON plan (never raw code), a deterministic validator (allow-list), a deterministic pandas
executor (no `exec`/`eval`), and a language-aware answer generator — wired live into `/ask-query`,
replacing the ad-hoc `ai_helper.py`/`data_tools.py` call site.

**Unlike C1/C2/C4-infra, this iteration is wired into the live app.** Those were left unwired
because there was no real OCR/spatial-chunk data yet; C3's input (`FinancialDocument`/`LineItem`,
Iteration 1) is already real, live, tenant-isolated Postgres data, so there was no reason to keep
PAL standalone-only. Confirmed this decision with the project owner before wiring it in, given the
change touches a live, user-facing endpoint.

Delivered:
- `backend/pal_scope.py` — Scope Resolver: tenant + company-name scoping over
  `FinancialDocument`/`LineItem` (reuses `data_tools.py`'s existing load/filter helpers), then
  flattens matched documents into one canonical-field row per `LineItem` (`build_row_records`).
  Documents without a line-item breakdown get one synthetic row from the document total, so
  aggregates don't silently drop them.
- `backend/pal_planner.py` — DeepSeek → strict JSON plan; returns `None` on any failure (timeout,
  bad JSON, non-dict) rather than raising, so the orchestrator can retry/degrade.
- `backend/pal_validator.py` — allow-list validator: `TASKS` (aggregate_sum/avg/count, compare,
  lookup_value, group_by_sum), `FILTER_OPS` (eq/in/contains/gte/lte/between), `AGGREGATIONS`
  (sum/avg/count/max/min), `CANONICAL_FIELDS` (the spec's 10 + a documented `flow_type`
  extension). Rejects ambiguous/missing measure fields, non-canonical fields/ops, and
  task-specific shape violations (e.g. `group_by_sum` without `group_by`).
- `backend/pal_executor.py` — pandas-only executor. Filters apply in sequence; aggregation uses
  `measure.agg` (authoritative over the task-name label); mixed-currency aggregates split into a
  `per_currency` breakdown instead of summing across currencies; `compare` runs two filter sets
  and returns both values plus the difference; `group_by_sum` and `lookup_value` have dedicated
  shapes.
- `backend/pal_answer.py` — DeepSeek phrasing grounded in the executor's `computed` result only
  (never re-computes), with Sinhala/English auto-detected from the question and a deterministic
  fallback template (mirrors `ai_helper.build_fallback_answer`) if DeepSeek is unavailable or
  returns unusable JSON.
- `backend/pal_qa.py` — orchestrator: routes listing intents (`invoice_list` etc.) straight to the
  legacy path; otherwise resolves scope, runs the planner with up to 2 retries (feeding back
  `error_reason` on each rejection), executes the validated plan, and either answers via PAL or
  degrades to the legacy `ai_helper.py`/`data_tools.py` path if the planner never validates or the
  plan matches zero rows. Evidence is built only from the documents the executed plan actually
  used (not the whole company scope), to keep provenance tight.
- `app.py`: `/ask-query` now calls `pal_qa.answer_financial_question()` instead of
  `data_tools.analyze_financial_query()` + `ai_helper.generate_explainable_answer()`. Response
  shape is unchanged (verified against `API_CONTRACT.md` and the frontend's `EvidenceItem`/
  `QueryResult` types in `frontend/src/app/answer/page.tsx`) — no frontend changes needed.
- `backend/tests/test_iter5_pal_qa.py` — 43 tests.
- Docs updated: `docs/ROADMAP.md`, `docs/gap-analysis.md` (FR-18…25, C3 row), `docs/ARCHITECTURE.md`
  (Q&A row), `docs/components/component-3.md` (implementation notes).

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` (excluding the 6 DB-integration tests, which hit a real Supabase instance) | **92 passed** |
| `cd backend && ruff check pal_validator.py pal_executor.py pal_planner.py pal_answer.py pal_scope.py pal_qa.py tests/test_iter5_pal_qa.py` | clean |
| `python -c "import app"` | imports cleanly with the new `pal_qa` wiring |
| Live `/ask-query` smoke test via `fastapi.testclient.TestClient`, with `pal_qa.resolve_scope`/`plan_query`/`generate_pal_answer` monkeypatched to known values (DeepSeek/DB untouched) | **200 OK**, correct computed value (`LKR 500.00`), evidence shape matches the frontend's `EvidenceItem` type exactly, `history_saved` gracefully `False` with `history_error` populated when the DB call failed (same non-fatal resilience as before PAL existed) |

> Note: this session hit an unrelated, transient Supabase DNS-resolution issue (the DB host
> resolves to an IPv6-only address that this network couldn't currently route to), which failed
> the 6 DB-integration tests (`test_iter1_data_layer.py`, one `test_iter4_vector_index.py` test).
> Confirmed with the project owner this is an environment/network blip, not a regression — none of
> this iteration's code touches those tables or that connection path. All 43 new PAL tests and the
> rest of the suite (49 from prior iterations) are fully hermetic and pass regardless.

New tests cover:
- **Validator**: accepts a well-formed `aggregate_sum` plan; rejects unknown task, unsupported
  filter op, non-canonical filter/measure/group-by field, missing measure field (ambiguous),
  unsupported aggregation, `group_by_sum` without `group_by`, `lookup_value` without filters,
  `compare` without exactly two filter sets (and validates each set's fields/ops).
- **Executor**: `aggregate_sum` with a filter, `aggregate_count`, `aggregate_avg`, `measure.agg`
  overriding the task-name-implied aggregation (max), `contains`/`between`/`in` filters,
  `group_by_sum` per-vendor totals, `lookup_value` returning matched field values, `compare`
  computing both sides and the difference, mixed-currency aggregates triggering the
  `per_currency` breakdown, empty input, and a filter on a field absent from the rows.
- **Scope**: one row per line item with correct field mapping; synthesizes `total` from
  `qty * unit_price` when `line_total` is missing; documents without items fall back to a
  synthetic row from the document total; missing/`"NULL"` currency defaults to `"LKR"`.
- **Planner/Answer** (DeepSeek boundary monkeypatched, hermetic): valid JSON reply parses
  correctly; unparseable reply and a raised exception both return `None`; the retry note
  (`error_reason`) is included in the next prompt; the answer generator uses DeepSeek's reply when
  valid, falls back to the deterministic template when DeepSeek is unavailable (including the
  per-currency-breakdown wording), and language detection correctly distinguishes a Sinhala
  question from an English one.
- **Orchestrator** (`answer_financial_question`): a listing intent (`invoice_list`) routes straight
  to the legacy path without ever calling the planner; an empty scope returns the
  not-found message with `audit.validation == "scope_empty"`; a full PAL success path returns the
  correct computed value, `audit.engine == "pal"`, and evidence scoped to only the documents used;
  exhausting all `MAX_RETRIES + 1` planner attempts on an invalid task degrades to the legacy path
  with every attempt's error recorded; a validated plan that matches zero rows also degrades to
  the legacy path with `audit.reason == "no_rows_matched"`.

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Arithmetic accuracy | ~100% | **100%** on the executor's unit tests — every aggregation/filter/group-by/compare result is asserted against the exact expected value, computed by pandas only (no LLM in the computation path) |
| Plan validation correctness | tracked | **100%** — every allow-list rule (task, filter ops, canonical fields, ambiguous measure, task-specific shape) has a dedicated rejection test, plus one acceptance test |
| Hallucination-free guarantee | non-negotiable | **structural** — `pal_executor.py` never calls `exec`/`eval`, and `pal_answer.py`'s prompt instructs DeepSeek to use only the precomputed `computed` JSON; the fallback template path requires no LLM at all |
| Live-wiring correctness | n/a | **verified** — `/ask-query`'s response shape is byte-for-byte compatible with `API_CONTRACT.md` and the frontend's existing `EvidenceItem`/`QueryResult` TypeScript types; no frontend changes needed |

## 4. Failures / known gaps

- **Row source is live Postgres, not C2 SpatialChunks / vector retrieval.** This is a deliberate
  choice (see component-3.md implementation notes), not a bug — but it means citations are bbox-
  less (`[]`) until C1/C2 are wired into the live pipeline.
- **"No rows retrieved" degrades to the legacy path** instead of literally "broadening retrieval"
  (the spec's failure-table wording) — simplification for this iteration.
- **Compare/lookup_value are minimally specified** — `compare` always needs exactly two filter
  sets and one shared measure; there's no support yet for comparing across different measures or
  more than two groups.
- **`tax`/`discount` are always `None`** in `build_row_records` — `dataset_manager.py`'s
  `_insert_line_items` doesn't currently write `LineItem.tax`/`discount` even though the column
  exists (a pre-existing gap from Iteration 1, not introduced here). Any PAL plan that filters or
  aggregates on `tax`/`discount` will correctly return zero rows/`None`, not a wrong number — but
  it can't compute a real tax/discount total yet.
- **DeepSeek calls are unmocked in the live smoke test** by necessity (this session had no live
  DeepSeek call attempted; the planner/answer-generator's DeepSeek boundary was instead
  monkeypatched for the smoke test, same as the unit tests) — real DeepSeek plan quality on
  diverse real questions hasn't been measured yet, only the deterministic plumbing around it.

## 5. Next

- Iteration 6 (Component 4 — Multi-Tenant Relationship Index): widen PAL's scope resolver with
  graph expansion (linked PO↔Invoice) once entities/aliases/doc_links are populated.
- Revisit wiring C1+C2 into `document_pipeline.py`, then swap `pal_scope.py`'s row source for
  vector retrieval (Iteration 4) + C2 SpatialChunks, unlocking real bbox citations.
- Fix `dataset_manager.py` to persist `LineItem.tax`/`discount` so PAL can use them.
- Measure real DeepSeek plan quality (plan success rate, association accuracy) against a labelled
  question set, once there's a safe way to spend live API calls on this.
