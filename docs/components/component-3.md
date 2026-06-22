# Component 3 — Neuro-Symbolic Arithmetic QA (PAL)

> Adapted from `docs/Research Components sme gpt.pdf` (Research Component 3).
> **Substitution:** planner and answer-generator LLM roles use the **DeepSeek API**.

## Purpose

Answer finance questions requiring arithmetic with **deterministic correctness**: the LLM produces
a **structured JSON plan** (never raw code), a validator checks it against an allow-list, a
deterministic executor (pandas) runs it, and an answer generator phrases the result in Sinhala/
English with **row-level provenance**. Runs at **query time**.

## Why

LLMs hallucinate arithmetic and field associations. PAL removes the LLM from the actual computation:
the LLM only *plans*; pandas *computes*.

## Inputs

- User query: `{ tenant_id, language, query, document_scope }`
- Candidate docs (from SQL date filter + C4): `[{doc_id, issue_date}, ...]`
- Retrieved spatial chunks (C2 + vector DB): `line_item_row`, `key_value`, optional `header`

## Output

```json
{ "answer_text": "...",
  "computed": { "value": 700.0, "currency": "LKR", "operation": "sum(line_item.total)",
                "rows_used": [ {"doc_id":"...","table_id":"t1","row_id":"row_007"} ] },
  "citations": [ {"doc_id":"...","page":1,"bbox":[110,290,610,345]} ],
  "audit": { "plan": { "task":"aggregate_sum" }, "validation": "passed" } }
```

## Flow

```
Query → Scope Resolver (if scope missing) → Retriever (vector) → Planner(LLM→JSON)
      → Validator (allow-list) → Executor (pandas) → Answer Generator(LLM) → response+citations+audit
```

## Plan schema (contract)

```json
{ "task": "aggregate_sum",
  "scope": { "doc_ids": ["INV_2025_0012","INV_2025_0030"] },
  "filters": [ {"field":"doc_date","op":"between","value":["2025-01-01","2025-01-31"]},
               {"field":"category","op":"eq","value":"fruit"} ],
  "measure": {"field":"total","agg":"sum"}, "group_by": [], "output": {"format":"currency"} }
```

- **Tasks:** `aggregate_sum, aggregate_avg, aggregate_count, compare, lookup_value, group_by_sum`
- **Filter ops:** `eq, in, contains, gte, lte, between`
- **Aggregations:** `sum, avg, count, max, min`
- **Canonical fields:** `item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor`

## Validator (symbolic guard)

Reject a plan if: task not in allow-list · unsupported operator · field not canonical · ambiguous
target field (unit_price vs total) unresolved · (optional) tenant-wide query without time constraint.
Output `validation_status` + `error_reason`.

## Executor

Load `row_records[]` (from `SpatialChunk.fields`) into a pandas DataFrame; apply filters +
aggregation **exactly**. No `exec`/`eval`. Return exact value + supporting rows.

## Retry & clarification

- On validation fail: send `error_reason` back to planner, retry up to **2×**.
- On unresolved ambiguity: ask the user OR pick a safe default and **disclose it**
  ("Assuming unit price…", "Assuming year=2025").

## Scope resolver (when `document_scope` is null)

1. SQL time filter (`issue_date`/`created_at`).
2. Optional graph expansion via C4 (linked PO↔Invoice).
→ `candidate_doc_ids[]`.

## Failure handling

| Failure | Fallback |
|---|---|
| No rows retrieved | broaden retrieval (more docs, lower threshold) |
| Missing required field | degrade to best available (e.g. sum invoice totals) |
| Conflicting currencies | per-currency totals + disclose |
| Unclear month/year | ask, or assume current year + disclose |

## Replaces

The ad-hoc logic in `backend/ai_helper.py` and `backend/data_tools.py`. `arithmetic_validator.py`
concepts fold into the executor/validator.

## Metrics

Arithmetic accuracy (~100% target), association accuracy, plan success rate, latency, explainability
(% answers with valid citations).

## Implementation notes (Iter 5)

- `backend/pal_scope.py` (Scope Resolver), `pal_planner.py` (Planner), `pal_validator.py`
  (Validator), `pal_executor.py` (Executor), `pal_answer.py` (Answer Generator), `pal_qa.py`
  (orchestrator, wired into `/ask-query` in `app.py`).
- **Row source is the live Postgres tables, not C2 SpatialChunks / vector retrieval.** The spec's
  "Inputs" section describes retrieving from C2 + the vector DB, but neither is wired into the
  live pipeline yet (no real OCR document to retrieve chunks from — see component-1.md/
  component-2.md). `FinancialDocument`+`LineItem` (Iteration 1) are real, tenant-isolated, and
  already carry the canonical fields, so `pal_scope.py` reads from there instead. The
  planner/validator/executor only consume canonical-field row dicts and don't care where they
  came from, so swapping in chunk-based retrieval later is a contained change to `pal_scope.py`
  alone.
- **Canonical-field allow-list extended with `flow_type`.** The literal 10-field list
  (`item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor`) has no
  field for payable/receivable/income/expense, which is core to almost every query this app
  answers ("how much do I owe X"). `company_name`-level scoping doesn't need a canonical field
  since `pal_scope.py` resolves it before the plan ever runs.
- **`measure.agg` is authoritative over the task name.** `TASKS` has no `aggregate_max`/
  `aggregate_min`, so "give me the max total" is expressed as `task: aggregate_sum` (a category
  label) + `measure.agg: max`. The executor always uses `measure.agg`, falling back to the
  task-implied aggregation only if `measure.agg` is missing (shouldn't happen given the
  validator).
- **Mixed currencies don't get summed together.** If an aggregate's matching rows span more than
  one currency, the executor returns `currency: "mixed"` plus a `per_currency` breakdown instead
  of a single (meaningless) cross-currency sum — this is the concrete form of the failure table's
  "Conflicting currencies -> per-currency totals + disclose".
- **"No rows retrieved" degrades to the legacy path** rather than literally "broadening retrieval"
  (the failure table's wording) — a simplification for this iteration, tracked in
  `docs/ROADMAP.md` as a follow-up.
- **Citations are empty (`[]`) for now** — bbox-level citations need C1/C2 wired into the live
  pipeline; until then there's no bbox to cite. Evidence (document-level) is still built and
  scoped to only the documents the executed plan actually used.
- **`arithmetic_validator.py` is unrelated and untouched.** It validates that an OCR-extracted
  document's total matches its summed line items at *ingestion* time
  (`document_pipeline.py`) — a different concern from PAL's *query-time* arithmetic. The
  "arithmetic_validator.py concepts fold into the executor/validator" line in this doc's original
  spec refers to the numeric-consistency-checking *idea*, not literal file replacement.
