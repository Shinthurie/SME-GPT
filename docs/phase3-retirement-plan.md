# Phase 3 — Retiring the legacy query engine (plan)

> Status legend: ✅ covered · 🟡 partial · ❌ missing

## Why this is a plan, not a PR

Phase 1 (`backend/agent/`, `POST /chat`) and Phase 2 (`/query/chat`) shipped a working,
feature-flagged conversational engine alongside the existing `/ask-query` (PAL Tier 1 + legacy
Tier 2). The obvious next step reads like "delete the old one" — but two things argue against
doing that yet:

1. **`/ask-query`'s response shape is load-bearing.** `frontend/src/app/answer/page.tsx` renders
   `metrics`, `explanation`, `source_file`, `computed`, `discrepancies`, and per-evidence
   `reason_used` — none of which the agent's `/chat` response produces (`answer` + `evidence`
   only, by design — the agent phrases a conversational reply, not a structured report). Rerouting
   `/ask-query` through the agent today means either breaking that page or faking the old shape
   around the new engine, which isn't retirement, just a disguise.
2. **The agent is unproven at scale.** In the first real session of live use, exercising it
   surfaced three latent, previously-unhit bugs shared with the legacy code paths: the LLM was
   silently routing query answers through local Ollama instead of the configured cloud provider,
   `pal_executor`'s date-range filter crashed on real-world date formats (never exercised by any
   prior test), and outstanding-balance queries overcounted already-paid amounts. All three are
   now fixed, but that track record argues for more real usage before removing the fallback that
   twice would have been the only thing standing between a user and a 500 or a wrong number.

So Phase 3 starts as a **parity map**: what the legacy engine's 22 `route_question()` intents
cover, what the agent's 3 tools (`aggregate_financials`, `search_documents`, `get_document_status`
in `backend/agent/tools.py`) already cover, and what's still missing. Retirement of any given
piece happens only once its replacement is ✅ here and has real usage behind it.

---

## Intent coverage

| Legacy intent (`data_tools.route_question`) | Agent coverage | Notes |
|---|---|---|
| `invoice_list` / `receipt_list` / `po_list` / `dn_list` | ✅ | `search_documents(document_type=...)` |
| `receivable` / `payable` | ✅ | `aggregate_financials` with `flow_type` + `paid_status`/`received_status` (fixed this session — see #61) |
| `cash_inflow` / `cash_outflow` / `expenses` / `revenue` | ✅ | `aggregate_financials` with the matching `flow_type` filter |
| `count_query` | ✅ | `aggregate_financials(agg="count")` |
| `document_lookup` | ✅ | `get_document_status(document_id)` |
| `po_status_query` / `invoice_status_query` / `dn_status_query` | 🟡 | Single-document status via `get_document_status`; listing "all pending POs"-style queries only work as far as the LLM can express it through `search_documents`'s free-text `query` param — there's no structured `status` filter arg |
| `date_range_query` | 🟡 | `aggregate_financials`'s `doc_date` `between`/`gte`/`lte` filters work (and are the most exercised/tested path); `search_documents` has no explicit `date_from`/`date_to` params, only free text |
| `payment_query` | 🟡 | Expressible via `aggregate_financials` + `paid_status` now, but there's no dedicated "payment history" grouping the way `handle_payment_query` provides |
| `summary` (default fallback) | 🟡 | The agent answers general questions fine conversationally, but doesn't replicate the legacy `matching_records`/`filtered_records` metrics breakdown |
| `supplier_query` | ❌ | No structured `vendor` filter param on `search_documents`; no equivalent of "top supplier by spend", supplier contact lookup, or supplier balance/history analytics |
| `customer_query` | ❌ | Same gap, customer side — "who owes us the most", customer contact lookup, customer history |
| `cross_document_query` | ❌ | No tool follows `order_id`/C4 entity-graph links (PO → DN → Invoice) the way `handle_cross_document_query` and `resolve_scope_with_c4`'s graph expansion do internally for scoping — nothing surfaces the relationship explicitly as an answerable query |
| `financial_comparison` | ❌ | `pal_executor.execute_plan` already supports a `"compare"` task (two filter sets + a delta) — it's just not exposed as an agent tool yet. Cheapest gap to close |
| `activity_query` | ❌ | No "what happened today/this week" / recent-documents tool |

**11 of 22 fully covered, 4 partial, 7 missing** (excluding `summary`, the default fallback, counted separately above).

---

## Closing the gaps — proposed tool additions (not yet built)

In rough order of value/effort:

- [ ] **`compare_financials` tool** — thin wrapper around `pal_executor`'s existing `"compare"`
      task. Closes `financial_comparison` for near-zero new logic; the executor already does this.
- [ ] **Structured filters on `search_documents`** — add `status`, `vendor`, `date_from`/`date_to`
      params instead of relying on free-text `query` alone. Closes the 🟡 status-query and
      date-range-listing gaps.
- [ ] **`get_related_documents(document_id)` tool** — wraps `entity_index.expand_related_docs`
      (already used internally by `resolve_scope_with_c4`) to surface PO↔Invoice↔DN links as an
      answerable query. Closes `cross_document_query`.
- [ ] **`get_party_summary(name, role="supplier"|"customer")` tool** — top supplier/customer by
      spend, contact info, outstanding balance. Closes `supplier_query`/`customer_query`; this is
      the largest net-new logic, not just a wrapper.
- [ ] **`recent_activity` tool** — "what happened today/this week", newest N documents. Closes
      `activity_query`.

## Retirement criteria (per piece, not all-at-once)

A legacy `handle_*` function / intent is safe to remove only when:
1. Its agent-tool replacement is ✅ in the table above, **and**
2. It's been exercised by real `/chat` usage (not just hermetic tests) without a correctness bug
   for a reasonable stretch — the same bar Phase 1's paid_status/date-filter bugs failed to clear
   on first real use, **and**
3. `/ask-query`'s response-shape constraint is resolved for that path — either `answer/page.tsx`
   stops depending on the fields only the legacy engine produces, or that page is retired in favor
   of `/query/chat` first.

`route_question()`'s keyword router and the legacy `handle_*` functions stay as the `/ask-query`
fallback until all three conditions hold for the intents they serve. `pal_planner`/PAL Tier 1 stays
as-is throughout — it isn't being replaced by the agent, it already shares the same executor/
validator the agent tools reuse.

## Non-goals for this plan

- Not touching `/ask-query`'s response contract or `answer/page.tsx` today.
- Not deleting any legacy code in this pass.
- Not making `/chat` the default UI entry point yet — `/query/chat` remains an opt-in "Beta" link
  from `/query` until the tool gaps above close and it accumulates real usage.
