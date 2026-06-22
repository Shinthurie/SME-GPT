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
