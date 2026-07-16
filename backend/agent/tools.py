"""Deterministic tools for the agentic query engine (Phase 1).

The LLM only ever *plans* by calling these tools; every number returned comes
from pal_executor's pandas arithmetic (aggregate_financials) or a direct,
unmodified row lookup (search_documents / get_document_status) -- never from
the LLM itself. This generalizes PAL's single rigid plan-execute cycle
(pal_planner -> pal_validator -> pal_executor -> pal_answer) into a set of
reusable, conversational tool calls while keeping the same safety boundary:
pal_validator.validate_plan() is still the authoritative gate before any
aggregation runs (docs/components/component-3.md "Why").

Tenant isolation (CLAUDE.md "Architecture Invariants"): user_id and
company_name are bound into these closures by build_tools() -- they are never
arguments the LLM can supply, so a prompt-injected or hallucinated user_id can
never leak another tenant's data.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

import data_tools as dt
from pal_executor import execute_plan
from pal_scope import build_row_records, resolve_scope_with_c4, resolve_scope_with_rag
from pal_validator import validate_plan

_AGG_TO_TASK = {"sum": "aggregate_sum", "avg": "aggregate_avg", "count": "aggregate_count"}


def build_tools(user_id: str, company_name: str) -> tuple[list, list[dict]]:
    """Returns (tools, evidence). `evidence` is a shared list the tools append
    to as they run (out-of-band from what the LLM sees) so the /chat endpoint
    can return the same EvidenceItem shape /ask-query already returns to the
    frontend. Call this once per request/thread -- the closures are not safe
    to share across users."""
    evidence: list[dict] = []

    @tool
    def aggregate_financials(
        measure_field: str,
        agg: str,
        filters: Optional[list[dict]] = None,
        group_by: Optional[list[str]] = None,
    ) -> dict:
        """Compute a deterministic financial total, average, count, max, or min over
        the user's saved financial documents (invoices, receipts, purchase orders,
        delivery notes) for the current company. This tool NEVER hallucinates a
        number -- it runs real pandas arithmetic. Use it for any "how much" /
        "how many" / "total" / "average" question; never answer those from memory.

        Args:
          measure_field: canonical field to aggregate. Use "total" for money
            amounts (almost always what "how much" questions want). Other
            options: qty, unit_price, tax, discount.
          agg: "sum" (total money), "avg" (average), "count" (how many),
            "max", "min".
          filters: list of {"field": ..., "op": ..., "value": ...} objects to
            narrow the rows. Canonical fields: item, description, qty,
            unit_price, total, tax, discount, currency, doc_date, vendor,
            flow_type. Ops: eq, in, contains, gte, lte, between. flow_type
            values: payable (we owe), receivable (owed to us), cash_inflow,
            cash_outflow -- for income/revenue use flow_type in [receivable,
            cash_inflow]; for expenses/spending use flow_type in [payable,
            cash_outflow]. For dates use {"field":"doc_date","op":"between",
            "value":["YYYY-MM-DD","YYYY-MM-DD"]} -- resolve relative periods
            ("this month", "last month", "this year") against today's date
            yourself before calling.
          group_by: optional list of canonical fields (e.g. ["vendor"]) to
            break the total down by group instead of a single number.

        Returns a dict with `value`, `currency`, `row_count`, and (if group_by
        was used) `groups`. If the arguments are invalid you get back an
        `error` explaining why -- fix the arguments and call again.
        """
        df, err = resolve_scope_with_c4(company_name, user_id)
        if err or df.empty:
            return {"error": err or "No documents found for this company."}

        rows = build_row_records(df)
        group_by = group_by or []
        task = "group_by_sum" if group_by else _AGG_TO_TASK.get(agg, "aggregate_sum")

        plan = {
            "task": task,
            "filters": filters or [],
            "measure": {"field": measure_field, "agg": agg},
            "group_by": group_by,
        }
        is_valid, reason = validate_plan(plan)
        if not is_valid:
            return {"error": f"Invalid arguments: {reason}. Use only canonical fields/ops."}

        computed = execute_plan(plan, rows)

        used_doc_ids = {r["document_id"] for r in computed.get("rows_used", [])}
        if used_doc_ids:
            evidence_df = df[df["document_id"].astype(str).isin(used_doc_ids)]
            evidence.extend(dt.build_evidence(
                evidence_df, f"Included by aggregate_financials({task}) over canonical fields."
            ))

        # Trim rows_used from what the LLM sees -- it only needs the computed
        # number(s), not every matched row; full evidence goes to the caller
        # separately via the `evidence` list above.
        return {
            "value": computed.get("value"),
            "currency": computed.get("currency"),
            "row_count": computed.get("row_count"),
            "operation": computed.get("operation"),
            "groups": computed.get("groups"),
            "per_currency": computed.get("per_currency"),
            "difference": computed.get("difference"),
        }

    @tool
    def search_documents(
        query: str = "",
        document_type: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """Find and list specific financial documents for the current company (e.g.
        "unpaid invoices from Virtusa", "delivery notes this month"). Use this when
        the user wants to SEE/LIST documents -- use aggregate_financials instead for
        totals/counts.

        Args:
          query: free-text description of what to find (used for semantic and
            keyword matching against the document set).
          document_type: optional filter -- one of invoice, receipt, po, dn.
          limit: max documents to return (default 10, capped at 50).

        Returns a dict with `documents` (list of matches: id, type, date,
        supplier, amount, currency, status fields) and `count`.
        """
        df, err = resolve_scope_with_rag(query, company_name, user_id)
        if err or df.empty:
            return {"documents": [], "count": 0, "note": err or "No documents found."}

        if document_type:
            df = df[df["document_type"].astype(str).str.lower() == document_type.strip().lower()]
            if df.empty:
                return {"documents": [], "count": 0, "note": f"No {document_type} documents found."}

        matched = df.head(max(1, min(limit, 50)))
        ev = dt.build_evidence(matched, f"Matched search_documents(query={query!r}).")
        evidence.extend(ev)

        summary = [
            {
                "document_id": e["document_id"],
                "document_type": e["document_type"],
                "date": e["date"],
                "supplier_name": e["supplier_name"],
                "amount": e["amount_used"],
                "currency": e["currency"],
                "po_status": e["po_status"],
                "dn_status": e["dn_status"],
                "invoice_status": e["invoice_status"],
            }
            for e in ev
        ]
        return {"documents": summary, "count": len(summary), "total_matches": int(len(df))}

    @tool
    def get_document_status(document_id: str) -> dict:
        """Look up ONE specific document by its ID (e.g. "INV-2045", "PO10045") and
        return its full status and details for the current company.

        Args:
          document_id: the document ID to look up (case-insensitive).
        """
        df, err = resolve_scope_with_c4(company_name, user_id)
        if err or df.empty:
            return {"error": err or "No documents found for this company."}

        match = df[df["document_id"].astype(str).str.lower() == document_id.strip().lower()]
        if match.empty:
            return {"error": f"No document found with ID '{document_id}'."}

        ev = dt.build_evidence(match, f"Direct lookup of document_id={document_id!r}.")
        evidence.extend(ev)
        return ev[0]

    return [aggregate_financials, search_documents, get_document_status], evidence
