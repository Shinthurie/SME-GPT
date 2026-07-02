"""Component 3 — Planner: DeepSeek -> strict JSON plan (never raw code).

The LLM only ever proposes a plan; it never computes anything
(docs/components/component-3.md "Why": LLMs hallucinate arithmetic, so PAL
removes them from computation entirely). On a validation failure, the
orchestrator (pal_qa.py) feeds the `error_reason` back here for a bounded
retry (component-3.md "Retry & clarification", up to 2x).
"""
from __future__ import annotations

import json

from llm_client import call_llm

_PLAN_SYSTEM = (
    "You are a financial query planner for a Sri Lankan SME system. "
    "You convert natural-language questions into strict JSON execution plans. "
    "You never compute results yourself — you only describe what to compute. "
    "You must return ONLY valid JSON, no prose, no markdown."
)

_PLAN_PROMPT = """You are a financial query planner for a Sri Lankan SME system. Convert the user's
question into a single JSON plan -- you never compute the answer yourself, you only describe what to compute.

LANGUAGE NOTE: The user may write in English, Sinhala, or a natural mix of both (very common in
Sri Lanka). Treat Sinhala words as their English semantic equivalents when planning:
  - "ගෙවිය යුතු" / "payable" → flow_type = payable
  - "ලැබිය යුතු" / "receivable" → flow_type = receivable
  - "කීයද" / "කීයක්" → aggregate count or sum
  - "මේ මාසේ" → current month date filter
  - "ගිය මාසේ" → previous month date filter
  - "වැඩියෙන්ම" → "highest" / "most"
  - "සැපයුම්කරු" → vendor/supplier
  - "ගනුදෙනුකරු" → customer/client

Allowed tasks: aggregate_sum, aggregate_avg, aggregate_count, compare, lookup_value, group_by_sum
Allowed filter ops: eq, in, contains, gte, lte, between
Allowed aggregations: sum, avg, count, max, min
Canonical fields ONLY (reject anything else): item, description, qty, unit_price, total, tax,
discount, currency, doc_date, vendor, flow_type, category
flow_type values: payable, receivable, cash_inflow, cash_outflow
category values: Revenue, Expenses
revenue/income queries → use flow_type in [receivable, cash_inflow]
expense/cost queries  → use flow_type in [payable, cash_outflow]

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

DATE FILTER EXAMPLES (use "between" with ISO dates "YYYY-MM-DD"):
Q: "Show invoices from February 2026"
→ {{"task":"aggregate_count","filters":[{{"field":"doc_date","op":"between","value":["2026-02-01","2026-02-28"]}},{{"field":"flow_type","op":"in","value":["receivable","cash_inflow"]}}],"measure":{{"field":"item","agg":"count"}},"group_by":[],"output":{{"format":"number"}}}}

Q: "Total spending in January 2026"
→ {{"task":"aggregate_sum","filters":[{{"field":"doc_date","op":"between","value":["2026-01-01","2026-01-31"]}},{{"field":"flow_type","op":"in","value":["payable","cash_outflow"]}}],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "Monthly breakdown of income this year"
→ {{"task":"group_by_sum","filters":[{{"field":"doc_date","op":"between","value":["2026-01-01","2026-12-31"]}},{{"field":"flow_type","op":"in","value":["receivable","cash_inflow"]}}],"measure":{{"field":"total","agg":"sum"}},"group_by":["doc_date"],"output":{{"format":"currency"}}}}

Q: "Unpaid invoices above LKR 50000 from Virtusa"
→ {{"task":"aggregate_sum","filters":[{{"field":"flow_type","op":"eq","value":"receivable"}},{{"field":"vendor","op":"contains","value":"Virtusa"}},{{"field":"total","op":"gte","value":50000}}],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "Compare spending this month vs last month"
→ {{"task":"compare","compare_filters":[[{{"field":"doc_date","op":"between","value":["2026-06-01","2026-06-30"]}},{{"field":"flow_type","op":"in","value":["payable","cash_outflow"]}}],[{{"field":"doc_date","op":"between","value":["2026-05-01","2026-05-31"]}},{{"field":"flow_type","op":"in","value":["payable","cash_outflow"]}}]],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "How many POs were issued in Q1 2026"
→ {{"task":"aggregate_count","filters":[{{"field":"doc_date","op":"between","value":["2026-01-01","2026-03-31"]}}],"measure":{{"field":"item","agg":"count"}},"group_by":[],"output":{{"format":"number"}}}}

Q: "Average invoice value from Classic Printers"
→ {{"task":"aggregate_avg","filters":[{{"field":"vendor","op":"contains","value":"Classic Printers"}}],"measure":{{"field":"total","agg":"avg"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "Top 3 suppliers by total spend"
→ {{"task":"group_by_sum","filters":[{{"field":"flow_type","op":"in","value":["payable","cash_outflow"]}}],"measure":{{"field":"total","agg":"sum"}},"group_by":["vendor"],"output":{{"format":"currency"}}}}

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
        raw_reply = call_llm(prompt, system=_PLAN_SYSTEM, format="json")
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
