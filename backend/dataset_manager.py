import os
import json
import pandas as pd

DATASET_PATH = "financial_documents_clean.csv"
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
]


def ensure_dataset_exists():
    if not os.path.exists(DATASET_PATH):
        df = pd.DataFrame(columns=DATASET_COLUMNS)
        df.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")
        return

    df = pd.read_csv(DATASET_PATH, keep_default_na=False)

    changed = False
    for col in DATASET_COLUMNS:
        if col not in df.columns:
            df[col] = "NULL"
            changed = True

    df = df[DATASET_COLUMNS]

    if changed:
        df.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")


def load_main_dataset():
    ensure_dataset_exists()
    df = pd.read_csv(DATASET_PATH, keep_default_na=False)

    for col in DATASET_COLUMNS:
        if col not in df.columns:
            df[col] = "NULL"

    return df[DATASET_COLUMNS]


def save_main_dataset(df):
    for col in DATASET_COLUMNS:
        if col not in df.columns:
            df[col] = "NULL"

    df = df[DATASET_COLUMNS]
    df.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")


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

    text = text.replace(",", "")
    text = text.replace("Rs.", "")
    text = text.replace("Rs", "")
    text = text.replace("LKR", "")
    text = text.replace("$", "")
    text = text.strip()

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
    text = " ".join(text.split())
    return text


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

    prefix_map = {
        "receipt": "R",
        "invoice": "IN",
        "po": "PO",
        "dn": "DN",
    }

    return prefix_map.get(doc_type, "DOC")


def generate_document_id(document_type: str) -> str:
    df = load_main_dataset()
    prefix = get_prefix_for_document_type(document_type)

    if df.empty or "document_id" not in df.columns:
        return f"{prefix}1"

    existing_ids = df["document_id"].astype(str).tolist()
    numbers = []

    for doc_id in existing_ids:
        doc_id = str(doc_id).strip()
        if doc_id.startswith(prefix):
            num_part = doc_id[len(prefix):]
            if num_part.isdigit():
                numbers.append(int(num_part))

    next_number = max(numbers) + 1 if numbers else 1
    return f"{prefix}{next_number}"


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
    }


def is_exact_duplicate(existing_row: dict, new_record: dict) -> bool:
    compare_text_fields = [
        "user_id",
        "document_type",
        "order_id",
        "flow_type",
        "company_name",
        "supplier_name",
        "date",
        "currency",
        "received_status",
        "paid_status",
        "status",
        "language",
        "raw_text",
        "corrected_text",
        "items_json",
    ]

    compare_number_fields = [
        "raw_total_amount",
        "final_total_amount",
        "payable_amount",
        "cash_return",
    ]

    for field in compare_text_fields:
        if normalize_compare_text(existing_row.get(field)) != normalize_compare_text(new_record.get(field)):
            return False

    for field in compare_number_fields:
        if normalize_compare_number(existing_row.get(field)) != normalize_compare_number(new_record.get(field)):
            return False

    return True


def find_duplicate_record(data: dict, user_id: str):
    df = load_main_dataset()
    if df.empty:
        return None

    new_record = normalize_record(data, user_id=user_id, force_generate_document_id=False)

    for _, row in df.iterrows():
        existing = row.to_dict()
        if is_exact_duplicate(existing, new_record):
            return existing

    return None


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


def load_all_records(user_id: str = None):
    df = load_main_dataset()

    if user_id is not None:
        df = df[df["user_id"].astype(str) == str(user_id)]

    if df.empty:
        return []

    records = [parse_record_for_output(r) for r in df.to_dict(orient="records")]
    return records


def get_record_by_id_for_user(user_id: str, document_id: str):
    df = load_main_dataset()

    filtered = df[
        (df["user_id"].astype(str) == str(user_id)) &
        (df["document_id"].astype(str) == str(document_id))
    ]

    if filtered.empty:
        return None

    record = filtered.iloc[0].to_dict()
    return parse_record_for_output(record)


def upsert_confirmed_record(data: dict, user_id: str):
    df = load_main_dataset()

    duplicate = find_duplicate_record(data, user_id=user_id)
    if duplicate:
        return {"action": "duplicate_exists", "record": parse_record_for_output(duplicate)}

    new_record = normalize_record(data, user_id=user_id, force_generate_document_id=True)
    new_row_df = pd.DataFrame([new_record], columns=DATASET_COLUMNS)
    updated_df = pd.concat([df, new_row_df], ignore_index=True)
    save_main_dataset(updated_df)

    return {"action": "inserted", "record": parse_record_for_output(new_record)}


def update_record_for_user(user_id: str, document_id: str, updates: dict):
    df = load_main_dataset()

    mask = (
        (df["user_id"].astype(str) == str(user_id)) &
        (df["document_id"].astype(str) == str(document_id))
    )

    if not mask.any():
        return None

    existing_row = df[mask].iloc[0].to_dict()

    existing_structured = {}
    try:
        existing_structured = json.loads(existing_row.get("structured_json", "{}"))
        if not isinstance(existing_structured, dict):
            existing_structured = {}
    except Exception:
        existing_structured = {}

    merged_structured = dict(existing_structured)
    merged_structured.update(updates)

    merged_record = dict(existing_row)

    for key, value in updates.items():
        if key == "items":
            merged_record["items_json"] = json.dumps(normalize_items(value), ensure_ascii=False).replace("\n", " ")
        elif key in DATASET_COLUMNS:
            merged_record[key] = value

    merged_record["structured_json"] = json.dumps(merged_structured, ensure_ascii=False).replace("\n", " ")

    for col in DATASET_COLUMNS:
        if col not in merged_record:
            merged_record[col] = "NULL"

    row_index = df[mask].index[0]
    for col in DATASET_COLUMNS:
        df.at[row_index, col] = merged_record.get(col, "NULL")

    save_main_dataset(df)
    return parse_record_for_output(merged_record)

def delete_record_for_user(user_id: str, document_id: str):
    df = load_main_dataset()

    mask = (
        (df["user_id"].astype(str) == str(user_id)) &
        (df["document_id"].astype(str) == str(document_id))
    )

    if not mask.any():
        return False

    df = df[~mask].copy()
    save_main_dataset(df)
    return True