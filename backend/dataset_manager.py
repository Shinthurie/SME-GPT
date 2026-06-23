"""Financial document data-access layer (Postgres / Supabase).

Iteration 1: replaces the previous CSV store with the Prisma-managed Postgres
schema (FinancialDocument + LineItem). The public API and the record shape are
preserved so app.py and data_tools.py keep working unchanged:

- records are dicts keyed by DATASET_COLUMNS (snake_case)
- missing values are the string "NULL"
- line items live in `items_json` (a JSON string)
- amounts are floats or "NULL"

All reads/writes are tenant-scoped (tenant_id == user_id). Deletes are soft
(`deletedAt`); soft-deleted rows are excluded everywhere.
"""

import os
import json

import pandas as pd
from psycopg.types.json import Jsonb

from db import get_conn, new_id

INCOMING_JSON_DIR = "incoming_json"

DATASET_COLUMNS = [
    "user_id",
    "document_id",
    "document_type",
    "order_id",
    "flow_type",
    "effective_flow_type",
    "company_name",
    "supplier_name",
    "date",
    "raw_total_amount",
    "final_total_amount",
    "total_status",
    "payable_amount",
    "cash_return",
    "currency",
    "received_status",
    "paid_status",
    "status",
    "language",
    "raw_text",
    "corrected_text",
    "items_json",
    "structured_json",
    "correction_json",
    "arithmetic_status",
    "arithmetic_json",
    "ocr_selected_version",
    "safe_boxes_json",
    "spatial_chunks_json",
]

# record key -> DB column (Prisma camelCase). items_json is handled separately.
RECORD_TO_DB = {
    "user_id": "tenantId",
    "document_id": "documentId",
    "document_type": "documentType",
    "order_id": "orderId",
    "flow_type": "flowType",
    "effective_flow_type": "effectiveFlowType",
    "company_name": "companyName",
    "supplier_name": "supplierName",
    "date": "docDate",
    "raw_total_amount": "rawTotalAmount",
    "final_total_amount": "finalTotalAmount",
    "total_status": "totalStatus",
    "payable_amount": "payableAmount",
    "cash_return": "cashReturn",
    "currency": "currency",
    "received_status": "receivedStatus",
    "paid_status": "paidStatus",
    "status": "status",
    "language": "language",
    "raw_text": "rawText",
    "corrected_text": "correctedText",
    "structured_json": "structuredJson",
    "correction_json": "correctionJson",
    "arithmetic_status": "arithmeticStatus",
    "arithmetic_json": "arithmeticJson",
    "ocr_selected_version": "ocrSelectedVersion",
    # Iteration 9 — spatial blobs (stored as TEXT, not JSONB)
    "safe_boxes_json": "safeboxJson",
    "spatial_chunks_json": "spatialChunksJson",
}

MONEY_FIELDS = {"raw_total_amount", "final_total_amount", "payable_amount", "cash_return"}
JSON_FIELDS = {"structured_json", "correction_json", "arithmetic_json"}


# ──────────────────────────── pure helpers (unchanged) ────────────────────────────

def save_input_json(json_data: dict, filename: str = "last_confirmed.json"):
    os.makedirs(INCOMING_JSON_DIR, exist_ok=True)
    path = os.path.join(INCOMING_JSON_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    return path


def flatten_text(text):
    if text is None:
        return "NULL"
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    text = text.strip()
    return text if text else "NULL"


def nullify_text(value):
    if value is None:
        return "NULL"
    text = str(value).strip()
    return text if text else "NULL"


def safe_to_float_or_null(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return "NULL"
    text = text.replace(",", "").replace("Rs.", "").replace("Rs", "")
    text = text.replace("LKR", "").replace("$", "").strip()
    if not text:
        return "NULL"
    try:
        return float(text)
    except Exception:
        return "NULL"


def normalize_compare_text(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    return " ".join(text.split())


def normalize_compare_number(value):
    parsed = safe_to_float_or_null(value)
    if parsed == "NULL":
        return "NULL"
    return float(parsed)


def normalize_items(items):
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append({
            "description": str(item.get("description", "")).strip(),
            "quantity": safe_to_float_or_null(item.get("quantity")),
            "unit_price": safe_to_float_or_null(item.get("unit_price")),
            "line_total": safe_to_float_or_null(item.get("line_total")),
        })
    return result


def get_prefix_for_document_type(document_type: str) -> str:
    if not isinstance(document_type, str):
        return "DOC"
    doc_type = document_type.lower().strip()
    prefix_map = {"receipt": "R", "invoice": "IN", "po": "PO", "dn": "DN"}
    return prefix_map.get(doc_type, "DOC")


def is_exact_duplicate(existing_row: dict, new_record: dict) -> bool:
    compare_text_fields = [
        "user_id", "document_type", "order_id", "flow_type", "company_name",
        "supplier_name", "date", "currency", "received_status", "paid_status",
        "status", "language", "raw_text", "corrected_text", "items_json",
    ]
    compare_number_fields = [
        "raw_total_amount", "final_total_amount", "payable_amount", "cash_return",
    ]
    for field in compare_text_fields:
        if normalize_compare_text(existing_row.get(field)) != normalize_compare_text(new_record.get(field)):
            return False
    for field in compare_number_fields:
        if normalize_compare_number(existing_row.get(field)) != normalize_compare_number(new_record.get(field)):
            return False
    return True


def normalize_record(data: dict, user_id: str, force_generate_document_id: bool = True) -> dict:
    document_type = nullify_text(data.get("document_type", None))
    if document_type == "NULL":
        document_type = "unknown"

    if force_generate_document_id:
        document_id = generate_document_id(document_type)
    else:
        document_id = nullify_text(data.get("document_id", None))

    raw_text = flatten_text(data.get("raw_text", None))
    corrected_text = flatten_text(data.get("corrected_text", None))

    raw_total = safe_to_float_or_null(data.get("raw_total_amount", None))
    final_total = safe_to_float_or_null(data.get("final_total_amount", None))
    payable_amount = safe_to_float_or_null(data.get("payable_amount", None))
    cash_return = safe_to_float_or_null(data.get("cash_return", None))

    if raw_total == "NULL" or final_total == "NULL":
        total_status = "NULL"
    else:
        total_status = "corrected" if final_total != raw_total else "original"

    items = normalize_items(data.get("items", []))
    arithmetic_validation = data.get("arithmetic_validation", {}) or {}

    structured_json = json.dumps(data, ensure_ascii=False).replace("\n", " ")
    correction_json = json.dumps({
        "total_check": {
            "raw_total_amount": raw_total,
            "final_total_amount": final_total,
            "status": total_status,
            "payable_amount": payable_amount,
            "cash_return": cash_return,
        }
    }, ensure_ascii=False).replace("\n", " ")
    arithmetic_json = json.dumps(arithmetic_validation, ensure_ascii=False).replace("\n", " ")

    return {
        "user_id": nullify_text(user_id),
        "document_id": document_id,
        "document_type": document_type,
        "order_id": nullify_text(data.get("order_id", None)),
        "flow_type": nullify_text(data.get("flow_type", None)),
        "effective_flow_type": nullify_text(
            data.get("effective_flow_type", data.get("flow_type", None))
        ),
        "company_name": nullify_text(data.get("company_name", None)),
        "supplier_name": nullify_text(data.get("supplier_name", None)),
        "date": nullify_text(data.get("date", None)),
        "raw_total_amount": raw_total,
        "final_total_amount": final_total,
        "total_status": total_status,
        "payable_amount": payable_amount,
        "cash_return": cash_return,
        "currency": nullify_text(data.get("currency", None)),
        "received_status": nullify_text(data.get("received_status", None)),
        "paid_status": nullify_text(data.get("paid_status", None)),
        "status": nullify_text(data.get("status", None)),
        "language": nullify_text(data.get("language", None)),
        "raw_text": raw_text,
        "corrected_text": corrected_text,
        "items_json": json.dumps(items, ensure_ascii=False).replace("\n", " "),
        "structured_json": structured_json if structured_json.strip() else "NULL",
        "correction_json": correction_json if correction_json.strip() else "NULL",
        "arithmetic_status": nullify_text(data.get("arithmetic_status", "not_checked")),
        "arithmetic_json": arithmetic_json if arithmetic_json.strip() else "NULL",
        "ocr_selected_version": nullify_text(data.get("ocr_selected_version", None)),
        # Iteration 9 — spatial blobs (large TEXT strings; NULL until doc is confirmed)
        "safe_boxes_json": nullify_text(data.get("safe_boxes_json", None)),
        "spatial_chunks_json": nullify_text(data.get("spatial_chunks_json", None)),
    }


def parse_record_for_output(record: dict):
    parsed = dict(record)
    try:
        items = json.loads(parsed.get("items_json", "[]"))
        parsed["items"] = items if isinstance(items, list) else []
    except Exception:
        parsed["items"] = []
    try:
        arithmetic = json.loads(parsed.get("arithmetic_json", "{}"))
        parsed["arithmetic_validation"] = arithmetic if isinstance(arithmetic, dict) else {}
    except Exception:
        parsed["arithmetic_validation"] = {}
    return parsed


# ──────────────────────────── DB <-> record conversion ────────────────────────────

def _to_db_text(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.upper() == "NULL":
        return None
    return text


def _to_db_money(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text == "" or text.upper() == "NULL":
        return None
    try:
        return float(text.replace(",", ""))
    except Exception:
        return None


def _to_db_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return Jsonb(value)
    text = str(value).strip()
    if text == "" or text.upper() == "NULL":
        return None
    try:
        return Jsonb(json.loads(text))
    except Exception:
        return None


def _from_db_text(value):
    if value is None:
        return "NULL"
    text = str(value)
    return text if text.strip() else "NULL"


def _from_db_money(value):
    if value is None:
        return "NULL"
    return float(value)


def _from_db_json(value):
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _record_to_db_value(record_key, value):
    if record_key in MONEY_FIELDS:
        return _to_db_money(value)
    if record_key in JSON_FIELDS:
        return _to_db_json(value)
    return _to_db_text(value)


def _li_to_item(li: dict) -> dict:
    return {
        "description": (li.get("description") or "").strip() if li.get("description") else "",
        "quantity": _from_db_money(li.get("qty")),
        "unit_price": _from_db_money(li.get("unitPrice")),
        "line_total": _from_db_money(li.get("total")),
    }


def _row_to_record(row: dict, items: list) -> dict:
    record = {}
    for rec_key, db_col in RECORD_TO_DB.items():
        raw = row.get(db_col)
        if rec_key in MONEY_FIELDS:
            record[rec_key] = _from_db_money(raw)
        elif rec_key in JSON_FIELDS:
            record[rec_key] = _from_db_json(raw)
        else:
            record[rec_key] = _from_db_text(raw)
    record["items_json"] = json.dumps(items, ensure_ascii=False)
    return record


# ──────────────────────────── reads ────────────────────────────

def load_records(user_id: str = None, document_id: str = None):
    where = ['"deletedAt" IS NULL']
    params = []
    if user_id is not None:
        where.append('"tenantId" = %s')
        params.append(str(user_id))
    if document_id is not None:
        where.append('"documentId" = %s')
        params.append(str(document_id))

    sql = f'SELECT * FROM "FinancialDocument" WHERE {" AND ".join(where)} ORDER BY "createdAt"'

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        docs = cur.fetchall()
        if not docs:
            return []
        doc_ids = [d["id"] for d in docs]
        cur.execute(
            'SELECT * FROM "LineItem" WHERE "documentRef" = ANY(%s) ORDER BY "lineNo"',
            (doc_ids,),
        )
        items_by_doc = {}
        for li in cur.fetchall():
            items_by_doc.setdefault(li["documentRef"], []).append(_li_to_item(li))

    return [_row_to_record(d, items_by_doc.get(d["id"], [])) for d in docs]


def load_main_dataset(user_id: str = None) -> pd.DataFrame:
    records = load_records(user_id=user_id)
    if not records:
        return pd.DataFrame(columns=DATASET_COLUMNS)
    df = pd.DataFrame(records)
    for col in DATASET_COLUMNS:
        if col not in df.columns:
            df[col] = "NULL"
    return df[DATASET_COLUMNS]


def load_all_records(user_id: str = None):
    return [parse_record_for_output(r) for r in load_records(user_id=user_id)]


def get_record_by_id_for_user(user_id: str, document_id: str):
    records = load_records(user_id=user_id, document_id=document_id)
    return parse_record_for_output(records[0]) if records else None


def generate_document_id(document_type: str) -> str:
    prefix = get_prefix_for_document_type(document_type)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT "documentId" FROM "FinancialDocument" WHERE "deletedAt" IS NULL')
        existing_ids = [str(r["documentId"]).strip() for r in cur.fetchall()]

    numbers = []
    for doc_id in existing_ids:
        if doc_id.startswith(prefix):
            num_part = doc_id[len(prefix):]
            if num_part.isdigit():
                numbers.append(int(num_part))
    next_number = max(numbers) + 1 if numbers else 1
    return f"{prefix}{next_number}"


def find_duplicate_record(data: dict, user_id: str):
    records = load_records(user_id=user_id)
    if not records:
        return None
    new_record = normalize_record(data, user_id=user_id, force_generate_document_id=False)
    for existing in records:
        if is_exact_duplicate(existing, new_record):
            return existing
    return None


# ──────────────────────────── writes ────────────────────────────

def _insert_line_items(cur, doc_pk: str, tenant_id, currency, items: list):
    for idx, item in enumerate(items, start=1):
        cur.execute(
            'INSERT INTO "LineItem" '
            '("id","tenantId","documentRef","lineNo","description","qty","unitPrice","total","currency") '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (
                new_id("li"),
                str(tenant_id),
                doc_pk,
                idx,
                (item.get("description") or "").strip() or None,
                _to_db_money(item.get("quantity")),
                _to_db_money(item.get("unit_price")),
                _to_db_money(item.get("line_total")),
                _to_db_text(currency),
            ),
        )


def upsert_confirmed_record(data: dict, user_id: str):
    duplicate = find_duplicate_record(data, user_id=user_id)
    if duplicate:
        return {"action": "duplicate_exists", "record": parse_record_for_output(duplicate)}

    record = normalize_record(data, user_id=user_id, force_generate_document_id=True)
    doc_pk = new_id("fd")

    db_values = {"id": doc_pk}
    for rec_key, db_col in RECORD_TO_DB.items():
        db_values[db_col] = _record_to_db_value(rec_key, record.get(rec_key))

    columns = list(db_values.keys())
    col_sql = ", ".join(f'"{c}"' for c in columns) + ', "updatedAt"'
    placeholders = ", ".join(["%s"] * len(columns)) + ", NOW()"
    sql = f'INSERT INTO "FinancialDocument" ({col_sql}) VALUES ({placeholders})'

    items = normalize_items(json.loads(record.get("items_json", "[]") or "[]"))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, list(db_values.values()))
        _insert_line_items(cur, doc_pk, record["user_id"], record.get("currency"), items)

    return {"action": "inserted", "record": parse_record_for_output(record)}


def update_record_for_user(user_id: str, document_id: str, updates: dict):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM "FinancialDocument" '
            'WHERE "tenantId" = %s AND "documentId" = %s AND "deletedAt" IS NULL',
            (str(user_id), str(document_id)),
        )
        row = cur.fetchone()
        if not row:
            return None
        doc_pk = row["id"]

        cur.execute(
            'SELECT * FROM "LineItem" WHERE "documentRef" = %s ORDER BY "lineNo"',
            (doc_pk,),
        )
        existing_items = [_li_to_item(li) for li in cur.fetchall()]
        existing_record = _row_to_record(row, existing_items)

        try:
            existing_structured = json.loads(existing_record.get("structured_json", "{}"))
            if not isinstance(existing_structured, dict):
                existing_structured = {}
        except Exception:
            existing_structured = {}

        merged_structured = dict(existing_structured)
        merged_structured.update(updates)

        merged_record = dict(existing_record)
        new_items = None
        for key, value in updates.items():
            if key == "items":
                new_items = normalize_items(value)
                merged_record["items_json"] = json.dumps(new_items, ensure_ascii=False).replace("\n", " ")
            elif key in DATASET_COLUMNS:
                merged_record[key] = value

        merged_record["structured_json"] = json.dumps(merged_structured, ensure_ascii=False).replace("\n", " ")

        set_cols = []
        set_vals = []
        for rec_key, db_col in RECORD_TO_DB.items():
            set_cols.append(f'"{db_col}" = %s')
            set_vals.append(_record_to_db_value(rec_key, merged_record.get(rec_key)))
        set_sql = ", ".join(set_cols) + ', "updatedAt" = NOW()'
        cur.execute(
            f'UPDATE "FinancialDocument" SET {set_sql} WHERE "id" = %s',
            set_vals + [doc_pk],
        )

        if new_items is not None:
            cur.execute('DELETE FROM "LineItem" WHERE "documentRef" = %s', (doc_pk,))
            _insert_line_items(cur, doc_pk, user_id, merged_record.get("currency"), new_items)

    return parse_record_for_output(merged_record)


def delete_record_for_user(user_id: str, document_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            'UPDATE "FinancialDocument" SET "deletedAt" = NOW(), "updatedAt" = NOW() '
            'WHERE "tenantId" = %s AND "documentId" = %s AND "deletedAt" IS NULL',
            (str(user_id), str(document_id)),
        )
        return cur.rowcount > 0
