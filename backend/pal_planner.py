"""Component 3 — Planner: DeepSeek -> strict JSON plan (never raw code).

The LLM only ever proposes a plan; it never computes anything
(docs/components/component-3.md "Why": LLMs hallucinate arithmetic, so PAL
removes them from computation entirely). On a validation failure, the
orchestrator (pal_qa.py) feeds the `error_reason` back here for a bounded
retry (component-3.md "Retry & clarification", up to 2x).
"""
from __future__ import annotations

import json

from ai_helper import call_ollama

_PLAN_PROMPT = """You are a financial query planner. Convert the user's question into a single
JSON plan -- you never compute the answer yourself, you only describe what to compute.

Allowed tasks: aggregate_sum, aggregate_avg, aggregate_count, compare, lookup_value, group_by_sum
Allowed filter ops: eq, in, contains, gte, lte, between
Allowed aggregations: sum, avg, count, max, min
Canonical fields ONLY (reject anything else): item, description, qty, unit_price, total, tax,
discount, currency, doc_date, vendor, flow_type
flow_type values: payable, receivable, income, expense

Return ONLY valid JSON, no prose, in this exact shape:
{{
  "task": "aggregate_sum",
  "filters": [ {{"field": "flow_type", "op": "eq", "value": "payable"}} ],
  "measure": {{"field": "total", "agg": "sum"}},
  "group_by": [],
  "output": {{"format": "currency"}}
}}

For "compare" tasks, use "compare_filters" (a list of exactly two filter lists) instead of
"filters":
{{"task": "compare", "compare_filters": [ [ {{...}} ], [ {{...}} ] ], "measure": {{"field": "total", "agg": "sum"}} }}

For "group_by_sum" tasks, set "group_by" to a non-empty list of canonical fields.
For "lookup_value" tasks, "filters" must narrow to the row(s) you want and "measure.field" is the
field to return (no "agg" needed).

User question:
{question}
{retry_note}
""".strip()


def plan_query(question: str, error_reason: str | None = None) -> dict | None:
    """Returns a parsed plan dict, or None if DeepSeek is unavailable or
    didn't return parseable JSON (the orchestrator treats None the same as a
    validation failure -- both consume a retry)."""
    retry_note = (
        f"\nYour previous plan was rejected: {error_reason}. Fix it and return a corrected plan."
        if error_reason else ""
    )
    prompt = _PLAN_PROMPT.format(question=question, retry_note=retry_note)

    try:
        raw_reply = call_ollama(prompt)
    except Exception:
        return None

    start, end = raw_reply.find("{"), raw_reply.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        plan = json.loads(raw_reply[start:end + 1])
    except Exception:
        return None

    return plan if isinstance(plan, dict) else None
