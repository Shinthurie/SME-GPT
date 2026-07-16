"""Component 3 — Planner: query LLM -> strict JSON plan (never raw code).

The query LLM is whatever llm_client.call_llm routes to (Gemini when
GEMINI_API_KEY is set, otherwise DeepSeek). There is no local fallback; if no
provider is available the planner returns no plan and pal_qa.py degrades to the
deterministic legacy engine.

The LLM only ever proposes a plan; it never computes anything
(docs/components/component-3.md "Why": LLMs hallucinate arithmetic, so PAL
removes them from computation entirely). On a validation failure, the
orchestrator (pal_qa.py) feeds the `error_reason` back here for a bounded
retry (component-3.md "Retry & clarification", up to 2x).
"""
from __future__ import annotations

import json
from datetime import date

from llm_client import call_llm

_PLAN_SYSTEM = (
    "You are a financial query planner for a Sri Lankan SME system. "
    "You convert natural-language questions into strict JSON execution plans. "
    "You never compute results yourself — you only describe what to compute. "
    "You must return ONLY valid JSON, no prose, no markdown."
)

_PLAN_PROMPT = """You are a financial query planner for a Sri Lankan SME system. Convert the user's
question into a single JSON plan -- you never compute the answer yourself, you only describe what to compute.

TODAY'S DATE is {today}. Resolve every relative period against this date and emit concrete ISO
dates in a "between" filter:
  - "today"        → [today, today]
  - "this week"    → Monday..Sunday of the current week
  - "this month"   → first..last day of the current month
  - "last month"   → first..last day of the previous month
  - "this year"    → Jan 1..Dec 31 of the current year
Never hardcode a year from the examples below — always compute from TODAY.

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
Allowed filter ops: eq, in, contains, gte, lte, between (there is no "not equal" -- express
exclusion with "in" over the values you DO want)
Allowed aggregations: sum, avg, count, max, min
Canonical fields ONLY (reject anything else): item, description, qty, unit_price, total, tax,
discount, currency, doc_date, vendor, flow_type, paid_status, received_status
flow_type values: payable (we owe), receivable (owed to us), cash_inflow (already received),
cash_outflow (already paid out)
revenue/income queries → use flow_type in [receivable, cash_inflow]
expense/cost HISTORY queries (money that has already moved) → use flow_type in [payable, cash_outflow]

OUTSTANDING (unpaid/unreceived) amounts -- NOT the same as spending/income history:
- "How much do we STILL owe" / outstanding payables: flow_type eq "payable" AND paid_status
  in ["not_paid", "partial"]. cash_outflow is already-paid money and must be excluded, and
  omitting the paid_status filter overcounts by including already-paid invoices/POs.
- "How much are we STILL owed" / outstanding receivables: flow_type eq "receivable" AND
  received_status in ["not_received", "partial"]. Omitting the filter overcounts by including
  amounts already received.

CHOOSING THE TASK (important):
- A "how much / total / what is our <money>" question (receivable, payable, revenue,
  spend, outstanding, balance, etc.) is ALWAYS aggregate_sum with
  measure {{"field": "total", "agg": "sum"}} -- NEVER lookup_value.
- A "how many / count" question is aggregate_count.
- lookup_value is ONLY for returning a stored field of one specific document
  (e.g. "what is the due date of invoice IN10"). Never use it to add up or count money.

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
→ {{"task":"aggregate_sum","filters":[{{"field":"flow_type","op":"eq","value":"receivable"}},{{"field":"received_status","op":"in","value":["not_received","partial"]}},{{"field":"vendor","op":"contains","value":"Virtusa"}},{{"field":"total","op":"gte","value":50000}}],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "What's the total receivable we have?" / "How much are we still owed?"
→ {{"task":"aggregate_sum","filters":[{{"field":"flow_type","op":"eq","value":"receivable"}},{{"field":"received_status","op":"in","value":["not_received","partial"]}}],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

Q: "How much do we owe in total?" / "What's our outstanding payable?"
→ {{"task":"aggregate_sum","filters":[{{"field":"flow_type","op":"eq","value":"payable"}},{{"field":"paid_status","op":"in","value":["not_paid","partial"]}}],"measure":{{"field":"total","agg":"sum"}},"group_by":[],"output":{{"format":"currency"}}}}

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
    """Returns a parsed plan dict, or None if the query LLM is unavailable or
    didn't return parseable JSON (the orchestrator treats None the same as a
    validation failure -- both consume a retry)."""
    retry_note = (
        f"\nYour previous plan was rejected: {error_reason}. Fix it and return a corrected plan."
        if error_reason else ""
    )
    prompt = _PLAN_PROMPT.format(
        question=question, retry_note=retry_note, today=date.today().isoformat()
    )

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
