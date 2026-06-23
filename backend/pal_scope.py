"""Component 3 — Scope Resolver + row-record builder (PAL Arithmetic QA).

Resolves "which documents/rows is this question about" before the PAL
planner ever runs, and flattens them into canonical-field row_records[] the
executor can load into a DataFrame (docs/components/component-3.md
"Executor").

Today this reads from the live, tenant-isolated Postgres tables
(FinancialDocument + LineItem, Iteration 1) via data_tools.py's existing
load/filter helpers -- not from C2 SpatialChunks / vector retrieval
(Iteration 3/4), since C1/C2 aren't wired into document_pipeline.py yet and
there's no real OCR document to retrieve chunks from. The planner,
validator, and executor only consume canonical-field row dicts and don't
care where they came from, so swapping in chunk-based retrieval later is a
contained change to this module alone.

Iteration 6: `resolve_scope_with_c4` extends `resolve_scope` with C4 graph
expansion (entity_index.expand_related_docs) to find cross-document links
(e.g. a PO linked to its invoice via a shared order_id or vendor entity).
"""
from __future__ import annotations

import pandas as pd

import data_tools as dt


def resolve_scope(company_name: str, user_id: str) -> tuple[pd.DataFrame, str | None]:
    """Tenant + company scoping. Returns (scoped_documents_df, error_message)
    -- error_message is None when scoping succeeded."""
    df = dt.load_dataset(user_id=user_id)
    user_df = dt.filter_user_context(df, user_id=user_id)
    if user_df.empty:
        return user_df, "No saved records found for the current user."

    company_df = dt.filter_company_context(user_df, company_name)
    if company_df.empty:
        return company_df, f"No records found for company '{company_name}' under the current user."

    return company_df, None


def resolve_scope_with_c4(company_name: str, user_id: str) -> tuple[pd.DataFrame, str | None]:
    """Tenant + company scoping + C4 graph expansion (Iteration 6).

    Calls resolve_scope() first, then follows DocLink edges to pull in
    additional documents that are linked to the initial result set (e.g.
    a PO linked to its invoice via shared order_id, or documents from the
    same vendor entity).  Degrades silently to the SQL-only path if the
    entity index is unreachable.
    """
    df, err = resolve_scope(company_name, user_id)
    if err or df.empty:
        return df, err

    try:
        from entity_index import expand_related_docs
        doc_ids = list(df["document_id"].dropna().astype(str).unique())
        expanded: set[str] = set(doc_ids)

        for did in doc_ids:
            for related in expand_related_docs(did, user_id):
                expanded.add(related)

        if len(expanded) > len(doc_ids):
            all_docs = dt.load_dataset(user_id=user_id)
            user_docs = dt.filter_user_context(all_docs, user_id=user_id)
            df = user_docs[user_docs["document_id"].astype(str).isin(expanded)].copy()
    except Exception:
        pass  # degrade to SQL-only scope if entity index is unavailable

    return df, None


def build_row_records(documents_df: pd.DataFrame) -> list[dict]:
    """One row per LineItem, joined with its parent document's canonical
    fields. Documents without a line-item breakdown get one synthetic row
    built from the document total, so aggregate queries don't silently drop
    them -- this matches the pre-PAL behavior in data_tools.sum_amounts,
    which always summed a document's total even without item detail."""
    rows: list[dict] = []
    for _, doc in documents_df.iterrows():
        currency = str(doc.get("currency") or "").strip()
        if currency.upper() in ("", "NULL", "NONE"):
            currency = "LKR"

        base = {
            "document_id": doc.get("document_id", "NULL"),
            "doc_date": doc.get("date", "NULL"),
            "vendor": doc.get("supplier_name", "NULL"),
            "flow_type": dt.normalize_flow(doc.get("flow_type")),
            "currency": currency,
        }

        items = dt.extract_items_from_row(doc)
        if items:
            for line_no, item in enumerate(items, start=1):
                qty = dt.to_float(item.get("quantity"))
                unit_price = dt.to_float(item.get("unit_price"))
                total = dt.to_float(item.get("line_total"))
                if total == 0.0 and qty and unit_price:
                    total = round(qty * unit_price, 2)
                description = item.get("description")
                description = description if description and description != "NULL" else "NULL"
                rows.append({
                    **base,
                    "line_no": line_no,
                    "item": description,
                    "description": description,
                    "qty": qty,
                    "unit_price": unit_price,
                    "total": total,
                    "tax": None,
                    "discount": None,
                })
        else:
            amount = dt.preferred_amount(doc)
            rows.append({
                **base,
                "line_no": None,
                "item": "NULL",
                "description": "NULL",
                "qty": 1.0,
                "unit_price": amount,
                "total": amount,
                "tax": None,
                "discount": None,
            })
    return rows
