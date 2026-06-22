import os
import json
import re
import pandas as pd

DATASET_PATH = "financial_documents_clean.csv"


def load_dataset():
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"{DATASET_PATH} not found.")

    df = pd.read_csv(DATASET_PATH, keep_default_na=False)
    return enrich_dataset(df)


def safe_json_load(value):
    if not value or str(value).strip() in ["", "NULL", "null", "None"]:
        return {}

    try:
        return json.loads(value)
    except Exception:
        return {}


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def to_float(value):
    if value is None:
        return 0.0

    text = str(value).strip()
    if text == "" or text.upper() == "NULL":
        return 0.0

    text = (
        text.replace(",", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("LKR", "")
        .replace("$", "")
        .strip()
    )

    try:
        return float(text)
    except Exception:
        return 0.0

def preferred_amount(row):
    # Query logic should prioritize final_total_amount
    amount = to_float(row.get("final_total_amount", 0))
    if amount == 0.0:
        amount = to_float(row.get("payable_amount", 0))
    if amount == 0.0:
        amount = to_float(row.get("raw_total_amount", 0))
    return amount


def extract_items_from_row(row):
    items = row.get("items", [])

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []

    if not isinstance(items, list):
        return []

    cleaned_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        cleaned_items.append({
            "description": item.get("description", "NULL"),
            "quantity": item.get("quantity", "NULL"),
            "unit_price": item.get("unit_price", "NULL"),
            "line_total": item.get("line_total", "NULL"),
        })

    return cleaned_items
def enrich_dataset(df: pd.DataFrame):
    if df.empty:
        for col in ["order_id", "flow_type", "received_status", "paid_status", "items"]:
            df[col] = []
        return df

    structured = (
        df["structured_json"].apply(safe_json_load)
        if "structured_json" in df.columns
        else pd.Series([{}] * len(df))
    )

    df = df.copy()
    df["order_id"] = structured.apply(lambda x: x.get("order_id", "NULL"))

    if "effective_flow_type" in df.columns:
        df["flow_type"] = df["effective_flow_type"].apply(
            lambda x: x if str(x).strip() not in ["", "NULL", "null", "None"] else None
        )
        df["flow_type"] = df["flow_type"].fillna(
            structured.apply(lambda x: x.get("flow_type", "unknown"))
        )
    else:
        df["flow_type"] = structured.apply(lambda x: x.get("flow_type", "unknown"))

    df["received_status"] = structured.apply(lambda x: x.get("received_status", "NULL"))
    df["paid_status"] = structured.apply(lambda x: x.get("paid_status", "NULL"))
    df["items"] = structured.apply(lambda x: x.get("items", []))

    numeric_cols = ["raw_total_amount", "final_total_amount", "payable_amount"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(to_float)

    for text_col in ["company_name", "supplier_name", "document_type", "date", "document_id"]:
        if text_col not in df.columns:
            df[text_col] = ""

    return df


def filter_user_context(df: pd.DataFrame, user_id: str):
    if "user_id" not in df.columns:
        return df.iloc[0:0].copy()

    return df[df["user_id"].astype(str) == str(user_id)].copy()


def filter_company_context(df: pd.DataFrame, company_name: str):
    target = normalize_text(company_name)
    if not target:
        return df.iloc[0:0].copy()

    return df[
        df["company_name"].apply(normalize_text).str.contains(target, na=False)
        | df["supplier_name"].apply(normalize_text).str.contains(target, na=False)
    ].copy()


def route_question(question: str):
    q = normalize_text(question)

    if any(term in q for term in ["receivable", "receive", "receiver", "received amount", "අයකරගත", "ලැබිය යුතු"]):
        return "receivable"

    if any(term in q for term in ["payable", "pay", "amount due", "ගෙවිය යුතු"]):
        return "payable"

    if any(term in q for term in ["invoice", "invoices", "show invoices"]):
        return "invoice_list"

    if any(term in q for term in ["receipt", "receipts", "show receipts"]):
        return "receipt_list"

    if any(term in q for term in ["po", "purchase order"]):
        return "po_list"

    if any(term in q for term in ["dn", "delivery note"]):
        return "dn_list"
    

    if any(term in q for term in ["expense", "expenses", "expence", "spent", "cost"]):
        return "expense"

    if any(term in q for term in ["income", "revenue", "earned"]):
        return "income"
    return "summary"


def normalize_flow(value):
    if not value:
        return "unknown"

    v = str(value).strip().lower()

    if v in ["receivable", "receive"]:
        return "receivable"
    if v in ["payable", "pay"]:
        return "payable"
    if v in ["income"]:
        return "income"
    if v in ["expense", "expence"]:
        return "expense"

    return "unknown"


def build_evidence(records: pd.DataFrame, reason: str):
    evidence = []

    for _, row in records.iterrows():
        amount_used = to_float(row.get("payable_amount", 0))
        if amount_used == 0.0:
            amount_used = to_float(row.get("final_total_amount", 0))
        if amount_used == 0.0:
            amount_used = to_float(row.get("raw_total_amount", 0))

        evidence.append({
            "document_id": row.get("document_id", "NULL"),
            "document_type": row.get("document_type", "NULL"),
            "date": row.get("date", "NULL"),
            "company_name": row.get("company_name", "NULL"),
            "supplier_name": row.get("supplier_name", "NULL"),
            "order_id": row.get("order_id", "NULL"),
            "flow_type": row.get("flow_type", "unknown"),
            "received_status": row.get("received_status", "NULL"),
            "paid_status": row.get("paid_status", "NULL"),
            "currency": row.get("currency", "NULL"),
            "final_total_amount": float(row.get("final_total_amount", 0) or 0),
            "payable_amount": float(row.get("payable_amount", 0) or 0),
            "amount_used": amount_used,
            "items": extract_items_from_row(row),
            "reason_used": reason,
        })

    return evidence


def extract_named_entity(question: str):
    q = normalize_text(question)

    patterns = [
        r"\bfrom\s+([a-zA-Z0-9 .,&'-]+)",
        r"\bby\s+([a-zA-Z0-9 .,&'-]+)",
        r"\bfor\s+([a-zA-Z0-9 .,&'-]+)",
        r"\bof\s+([a-zA-Z0-9 .,&'-]+)",
    ]

    stop_words = {
        "company", "invoice", "invoices", "receipt", "receipts", "po", "dn",
        "payable", "receivable", "amount", "total", "documents", "document",
        "we", "have", "what", "is", "the", "a", "an"
    }

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            candidate = normalize_text(match.group(1))
            candidate_words = [w for w in candidate.split() if w not in stop_words]
            candidate = " ".join(candidate_words).strip()
            if candidate:
                return candidate

    return ""


def filter_named_entity(records: pd.DataFrame, entity_name: str):
    target = normalize_text(entity_name)
    if not target:
        return records.copy()

    company_match = records["company_name"].apply(normalize_text).str.contains(target, na=False)
    supplier_match = records["supplier_name"].apply(normalize_text).str.contains(target, na=False)

    filtered = records[company_match | supplier_match].copy()
    return filtered


def sum_amounts(records: pd.DataFrame):
    total_amount = 0.0

    for _, row in records.iterrows():
        amount = preferred_amount(row)
        total_amount += amount

    return round(total_amount, 2)

def wants_items(question: str):
    q = normalize_text(question)
    return any(word in q for word in [
        "item", "items", "product", "products", "description", "breakdown",
        "separately", "separate", "each", "details", "detail",
        "අයිතම", "වෙන වෙනම", "විස්තර"
    ])


def build_direct_answer(records: pd.DataFrame, question_type: str, company_name: str, question: str):
    if records.empty:
        return "No matching records found."

    show_items = wants_items(question)
    total = sum_amounts(records)

    lines = []

    for _, row in records.iterrows():
        doc_id = row.get("document_id", "NULL")
        supplier = row.get("supplier_name", "NULL")
        doc_type = row.get("document_type", "NULL")
        flow = row.get("flow_type", "NULL")
        currency = row.get("currency", "LKR")
        amount = preferred_amount(row)

        if str(currency).strip().upper() in ["", "NULL", "NONE"]:
            currency = "LKR"

        lines.append(f"{doc_id} - {supplier} ({doc_type}, {flow}): {currency} {amount}")

        if show_items:
            items = extract_items_from_row(row)

            if items:
                for item in items:
                    desc = item.get("description", "NULL")
                    qty = item.get("quantity", "NULL")
                    unit_price = item.get("unit_price", "NULL")
                    line_total = item.get("line_total", "NULL")
                    lines.append(
                        f"  - {desc} | Qty: {qty} | Unit Price: {unit_price} | Line Total: {line_total}"
                    )
            else:
                lines.append("  - No item details found for this document.")

    if question_type == "receivable":
        lines.append(f"Total Receivable: LKR {total}")
    elif question_type == "payable":
        lines.append(f"Total Payable: LKR {total}")
    elif question_type == "expense":
        lines.append(f"Total Expense: LKR {total}")
    elif question_type == "income":
        lines.append(f"Total Income: LKR {total}")
    else:
        lines.append(f"Total: LKR {total}")

    return "\n".join(lines)

def analyze_financial_query(question: str, company_name: str, user_id: str):
    df = load_dataset()
    user_df = filter_user_context(df, user_id=user_id)

    if user_df.empty:
        return {
            "success": False,
            "question_type": "none",
            "explanation": "No saved records found for the current user.",
            "evidence": [],
            "metrics": {},
            "source_file": DATASET_PATH,
        }

    company_df = filter_company_context(user_df, company_name)

    if company_df.empty:
        return {
            "success": False,
            "question_type": "none",
            "explanation": f"No records found for company '{company_name}' under the current user.",
            "evidence": [],
            "metrics": {},
            "source_file": DATASET_PATH,
        }

    question_type = route_question(question)
    entity_name = extract_named_entity(question)

    filtered_df = company_df.copy()
    entity_filter_applied = False

    if entity_name:
        candidate_df = filter_named_entity(company_df, entity_name)
        if not candidate_df.empty:
            filtered_df = candidate_df
            entity_filter_applied = True

    if question_type in ["expense", "income"]:
        result_df = filtered_df[
            filtered_df["flow_type"].apply(normalize_flow) == question_type
        ].copy()

        total_amount = sum_amounts(result_df)

        reason = f"Included because current user matched, company matched, and flow_type is {question_type}."
        if entity_filter_applied:
            reason = f"Included because current user matched, company matched, flow_type is {question_type}, and entity matched '{entity_name}'."

        return {
            "success": True,
            "question_type": question_type,
            "direct_answer": build_direct_answer(result_df, question_type, company_name, question),
            "explanation": (
                f"Computed {question_type} records for company '{company_name}' using only the current user's matching documents."
                + (f" Applied extra entity filter for '{entity_name}'." if entity_filter_applied else "")
            ),
            "evidence": build_evidence(result_df, reason),
            "metrics": {
                "company_name": company_name,
                "matching_records": int(len(result_df)),
                "filtered_records": int(len(result_df)),
                f"{question_type}_documents": int(len(result_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
                f"total_{question_type}_amount": total_amount,
            },
            "source_file": DATASET_PATH,
        }

    if question_type == "receivable":
        receivable_df = filtered_df[filtered_df["flow_type"].apply(normalize_flow) == "receivable"].copy()

        if "received_status" in receivable_df.columns:
            outstanding_df = receivable_df[
                receivable_df["received_status"].apply(normalize_text) != "received"
            ].copy()
        else:
            outstanding_df = receivable_df.copy()

        total_amount = sum_amounts(outstanding_df)

        reason = "Included because current user matched, company matched, and flow_type is receivable."
        if entity_filter_applied:
            reason = f"Included because current user matched, company matched, flow_type is receivable, and entity matched '{entity_name}'."

        return {
            "success": True,
            "question_type": "receivable",
            "explanation": (
                f"Computed receivable amount for company '{company_name}' using only the current user's receivable documents."
                + (f" Applied extra entity filter for '{entity_name}'." if entity_filter_applied else "")
            ),
            "evidence": build_evidence(outstanding_df, reason),
            "metrics": {
                "company_name": company_name,
                "matching_records": int(len(company_df)),
                "filtered_records": int(len(filtered_df)),
                "receivable_documents": int(len(outstanding_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
                "total_receivable_amount": total_amount,
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(outstanding_df, "receivable", company_name, question),
        }

    if question_type == "payable":
        payable_df = filtered_df[filtered_df["flow_type"].apply(normalize_flow) == "payable"].copy()

        if "paid_status" in payable_df.columns:
            outstanding_df = payable_df[
                payable_df["paid_status"].apply(normalize_text) != "paid"
            ].copy()
        else:
            outstanding_df = payable_df.copy()

        total_amount = sum_amounts(outstanding_df)

        reason = "Included because current user matched, company matched, and flow_type is payable."
        if entity_filter_applied:
            reason = f"Included because current user matched, company matched, flow_type is payable, and entity matched '{entity_name}'."

        return {
            "success": True,
            "question_type": "payable",
            "explanation": (
                f"Computed payable amount for company '{company_name}' using only the current user's payable documents."
                + (f" Applied extra entity filter for '{entity_name}'." if entity_filter_applied else "")
            ),
            "evidence": build_evidence(outstanding_df, reason),
            "metrics": {
                "company_name": company_name,
                "matching_records": int(len(company_df)),
                "filtered_records": int(len(filtered_df)),
                "payable_documents": int(len(outstanding_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
                "total_payable_amount": total_amount,
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(outstanding_df, "payable", company_name, question),
        }

    if question_type == "invoice_list":
        result_df = filtered_df[filtered_df["document_type"].apply(normalize_text) == "invoice"].copy()
        return {
            "success": True,
            "question_type": "invoice_list",
            "explanation": f"Listed invoices for company '{company_name}' using only the current user's records.",
            "evidence": build_evidence(
                result_df,
                "Included because current user matched, company matched, and document_type is invoice."
            ),
            "metrics": {
                "company_name": company_name,
                "invoice_count": int(len(result_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(result_df, "invoice_list", company_name, question),
        }

    if question_type == "receipt_list":
        result_df = filtered_df[filtered_df["document_type"].apply(normalize_text) == "receipt"].copy()
        return {
            "success": True,
            "question_type": "receipt_list",
            "explanation": f"Listed receipts for company '{company_name}' using only the current user's records.",
            "evidence": build_evidence(
                result_df,
                "Included because current user matched, company matched, and document_type is receipt."
            ),
            "metrics": {
                "company_name": company_name,
                "receipt_count": int(len(result_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(result_df, "receipt_list", company_name, question),
        }

    if question_type == "po_list":
        result_df = filtered_df[filtered_df["document_type"].apply(normalize_text) == "po"].copy()
        return {
            "success": True,
            "question_type": "po_list",
            "explanation": f"Listed purchase orders for company '{company_name}' using only the current user's records.",
            "evidence": build_evidence(
                result_df,
                "Included because current user matched, company matched, and document_type is po."
            ),
            "metrics": {
                "company_name": company_name,
                "po_count": int(len(result_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(result_df, "po_list", company_name, question),
        }

    if question_type == "dn_list":
        result_df = filtered_df[filtered_df["document_type"].apply(normalize_text) == "dn"].copy()
        return {
            "success": True,
            "question_type": "dn_list",
            "explanation": f"Listed delivery notes for company '{company_name}' using only the current user's records.",
            "evidence": build_evidence(
                result_df,
                "Included because current user matched, company matched, and document_type is dn."
            ),
            "metrics": {
                "company_name": company_name,
                "dn_count": int(len(result_df)),
                "entity_filter": entity_name if entity_filter_applied else "",
            },
            "source_file": DATASET_PATH,
            "direct_answer": build_direct_answer(result_df, "dn_list", company_name, question),
        }

    result_df = filtered_df.copy()
    return {
        "success": True,
        "question_type": "summary",
        "explanation": f"Generated a summary using only the current user's matching records for company '{company_name}'.",
        "evidence": build_evidence(
            result_df,
            "Included because current user matched and company matched."
            + (f" Entity filter '{entity_name}' was also applied." if entity_filter_applied else "")
        ),
        "metrics": {
            "company_name": company_name,
            "matching_records": int(len(company_df)),
            "filtered_records": int(len(filtered_df)),
            "entity_filter": entity_name if entity_filter_applied else "",
        },
        "source_file": DATASET_PATH,
        "direct_answer": build_direct_answer(result_df, "summary", company_name, question),
    }