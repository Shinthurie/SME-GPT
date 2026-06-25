import json
import os
import re
import requests
from llm_correction import clean_ocr_text

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_HOST = "https://api.deepseek.com"


def call_ollama(prompt: str) -> str:
    url = f"{DEEPSEEK_HOST}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "stream": False,
            },
            timeout=600,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Could not connect to DeepSeek API. Error: {e}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"DeepSeek HTTP error: {e}. Response: {response.text}")
    except requests.exceptions.Timeout:
        raise Exception("DeepSeek extraction request timed out.")


def extract_json_block(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("LLM response is not a string.")

    # First try direct object extraction
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    # If no JSON found, fail with clearer message
    raise ValueError(
        "No valid JSON object found in LLM response. "
        "The model likely returned conversational text instead of structured output.\n"
        f"Response preview:\n{text[:1500]}"
    )

def clean_json_string(json_text: str) -> str:
    if not isinstance(json_text, str):
        return ""

    fixed = json_text.strip()
    fixed = fixed.replace("```json", "").replace("```", "").strip()
    fixed = fixed.replace("“", '"').replace("”", '"')
    fixed = fixed.replace("‘", "'").replace("’", "'")
    fixed = re.sub(r"\bNone\b", "null", fixed)
    fixed = re.sub(r"\bTrue\b", "true", fixed)
    fixed = re.sub(r"\bFalse\b", "false", fixed)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    return fixed

def normalize_ocr_money(value):
    if value is None:
        return "NULL"

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return "NULL"

    text = text.replace(",", "").replace("Rs.", "").replace("Rs", "").replace("LKR", "").strip()

    # OCR receipt fix:
    # ".300" on receipt totals is often a broken OCR read of "1300"
    if re.fullmatch(r"\.\d{3}", text):
        return int("1" + text[1:])

    try:
        return float(text) if "." in text else int(text)
    except Exception:
        return "NULL"

def normalize_number(value):
    if value is None:
        return "NULL"

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "").replace("Rs.", "").replace("Rs", "").replace("LKR", "").strip()

    if text == "":
        return "NULL"

    try:
        return float(text) if "." in text else int(text)
    except Exception:
        return "NULL"


def detect_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"

    has_sinhala = bool(re.search(r"[\u0D80-\u0DFF]", text))
    has_english = bool(re.search(r"[A-Za-z]", text))

    if has_sinhala and has_english:
        return "si-en"
    if has_sinhala:
        return "si"
    if has_english:
        return "en"

    return "unknown"


def normalize_items(items):
    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue

        result.append({
            "description": str(item.get("description", "")).strip(),
            "quantity": normalize_number(item.get("quantity")),
            "unit_price": normalize_number(item.get("unit_price")),
            "line_total": normalize_number(item.get("line_total")),
        })

    return result

def detect_document_type_from_text(text: str) -> str:
    if not isinstance(text, str):
        return "unknown"

    lower = text.lower()

    if "invoice" in lower:
        return "invoice"

    if "purchase order" in lower or re.search(r"\bpo\b", lower):
        return "po"

    if "delivery note" in lower or re.search(r"\bdn\b", lower):
        return "dn"

    receipt_signals = 0

    if "cash return" in lower:
        receipt_signals += 2
    if "total" in lower:
        receipt_signals += 1
    if "date" in lower:
        receipt_signals += 1
    if "order id" in lower:
        receipt_signals += 1
    if re.search(r"^\s*\d+\s+", text, flags=re.MULTILINE):
        receipt_signals += 1

    if receipt_signals >= 3:
        return "receipt"

    return "unknown"

def infer_company_name_from_text(source_text: str, current_company: str) -> str:
    current_company = str(current_company or "").strip()
    lines = [ln.strip() for ln in str(source_text or "").splitlines() if ln.strip()]

    business_keywords = [
        "සැලෝන්", "salon", "shop", "stores", "store",
        "pharmacy", "hotel", "restaurant", "mart", "traders"
    ]

    top_lines = lines[:8]

    # First try current parsed value if it already looks like a business
    if current_company:
        lower_current = current_company.lower()
        if any(keyword in lower_current for keyword in business_keywords):
            return current_company

    # Then prefer top OCR lines that look like business names
    for line in top_lines:
        lower = line.lower()
        if any(keyword in lower for keyword in business_keywords):
            return line

    # If first 2–3 top lines look like a stacked business name, join them
    if len(top_lines) >= 2:
        joined = " ".join(top_lines[:2]).strip()
        if joined:
            return joined

    return current_company if current_company else "Customer"

def normalize_supplier_name(value: str) -> str:
    text = str(value or "").strip()
    if not text or text.upper() == "NULL" or text.lower() == "unknown":
        return "Customer"
    return text


def normalize_root_fields(parsed: dict, source_text: str) -> dict:
    if not isinstance(parsed, dict):
        return {}

    language = detect_language(source_text)

    document_type = str(parsed.get("document_type", "unknown")).strip().lower() or "unknown"

    if document_type == "unknown":
        document_type = detect_document_type_from_text(source_text)
    if document_type in {"purchase order", "purchase_order"}:
        document_type = "po"
    if document_type in {"delivery note", "delivery_note"}:
        document_type = "dn"

    flow_type = str(parsed.get("flow_type", "unknown")).strip().lower() or "unknown"
    if flow_type == "expence":
        flow_type = "expense"

    return {
        "document_id": str(parsed.get("document_id", "")).strip(),
        "document_type": document_type,
        "order_id": str(parsed.get("order_id", "")).strip(),
        "flow_type": flow_type,
        "company_name": infer_company_name_from_text(
            source_text,
            str(parsed.get("company_name", "")).strip()
        ),
        "supplier_name": normalize_supplier_name(
            str(parsed.get("supplier_name", "")).strip()
        ),
        "date": str(parsed.get("date", "")).strip(),
        "currency": str(parsed.get("currency", "")).strip(),
        "raw_total_amount": normalize_ocr_money(parsed.get("raw_total_amount")),
        "final_total_amount": normalize_ocr_money(parsed.get("final_total_amount")),
        "payable_amount": normalize_ocr_money(parsed.get("payable_amount")),
        "cash_return": normalize_number(parsed.get("cash_return")),
        "received_status": str(parsed.get("received_status", "")).strip(),
        "paid_status": str(parsed.get("paid_status", "")).strip(),
        "language": language,
        "items": normalize_items(parsed.get("items", [])),
    }

def retry_extract_json_only(raw_text: str) -> str:
    retry_prompt = f"""
Return ONLY one valid JSON object — no markdown, no explanations, no notes.

Extract ALL line items. For each item row extract:
- description (item name)
- quantity (Qty/QTY/Nos/Pcs/Units/ප්‍රමාණය)
- unit_price (Rate/Price/Unit Rate/Unit Price/ඒකක මිල)
- line_total (Amount/Total/රු.)

Use "" for any missing field. Do NOT skip item rows.
Default currency to "LKR" if not stated.

{{
  "document_id": "",
  "document_type": "unknown",
  "order_id": "",
  "flow_type": "unknown",
  "company_name": "",
  "supplier_name": "",
  "date": "",
  "currency": "LKR",
  "raw_total_amount": "",
  "final_total_amount": "",
  "payable_amount": "",
  "cash_return": "",
  "received_status": "",
  "paid_status": "",
  "items": [
    {{
      "description": "",
      "quantity": "",
      "unit_price": "",
      "line_total": ""
    }}
  ]
}}

OCR text:
{raw_text}
""".strip()

    return call_ollama(retry_prompt)


def extract_structured_json_from_text(raw_text: str) -> dict:
    cleaned_text = clean_ocr_text(raw_text)

    prompt = f"""
You are a precise financial document extraction engine. Extract structured data from OCR text.

Return ONLY one valid JSON object — no explanations, no notes.

CRITICAL RULES:
- Copy values EXACTLY from the OCR text
- Preserve ALL Sinhala characters in Sinhala Unicode script
- Do NOT translate, transliterate, or replace Sinhala text
- Do NOT calculate or invent numbers
- Do NOT add values not present in the text
- Use "" for any field not found in the text

DOCUMENT TYPE (pick one):
- "invoice"  → document header says Invoice/Bill/Tax Invoice
- "receipt"  → short shop bill, cash receipt, POS receipt, salon/restaurant bill
- "po"       → Purchase Order / PO
- "dn"       → Delivery Note / Goods Received Note
- "unknown"  → if none of the above

FLOW TYPE (pick one):
- "payable"    → we owe money to a supplier (we are the buyer)
- "receivable" → a customer owes us money (we are the seller)
- "expense"    → already paid retail bill / cash purchase
- "income"     → money already received from a customer
- "unknown"    → when unclear

FIELD EXTRACTION GUIDE:
- company_name: the business that ISSUED this document (top of page, usually largest text)
- supplier_name: the party on the other side (buyer for invoices, seller for receipts)
- order_id: any invoice number, receipt number, PO number, bill number, reference number
- date: the document date in any format found

LINE ITEMS — THIS IS CRITICAL:
Each item row in the document must be a separate object in "items".
For EACH item look for these columns (they may use different labels):
  - description: item name/product/service (required — always extract)
  - quantity: amount/count (also labeled as: Qty, QTY, Nos, No., Pcs, Units, Count, ප්‍රමාණය)
  - unit_price: price per unit (also labeled as: Rate, Unit Rate, Price, U/Price, Unit Price, ඒකක මිල, මිල)
  - line_total: row total / amount (also labeled as: Amount, Total, Line Total, Sub, රු.)
If a column is missing from a row, use "" — do NOT skip the item row entirely.
For receipts with no explicit qty column: assume quantity = 1 if only price and total are given.
Extract ALL item rows visible in the document — do not skip any.

AMOUNT FIELDS:
- raw_total_amount: the grand total as it appears in the OCR
- final_total_amount: same as raw_total_amount unless a discount is applied
- payable_amount: amount the buyer must pay (after discount, if any)
- cash_return: change given back to customer (if shown)
- currency: LKR, USD, EUR etc. (default LKR if not stated)

Return this JSON structure:
{{
  "document_id": "",
  "document_type": "unknown",
  "order_id": "",
  "flow_type": "unknown",
  "company_name": "",
  "supplier_name": "",
  "date": "",
  "currency": "LKR",
  "raw_total_amount": "",
  "final_total_amount": "",
  "payable_amount": "",
  "cash_return": "",
  "received_status": "",
  "paid_status": "",
  "items": [
    {{
      "description": "",
      "quantity": "",
      "unit_price": "",
      "line_total": ""
    }}
  ]
}}

OCR text:
{cleaned_text}
""".strip()

    llm_response = call_ollama(prompt)

    try:
        json_block = extract_json_block(llm_response)
    except ValueError:
        llm_response = retry_extract_json_only(cleaned_text)
        json_block = extract_json_block(llm_response)

    cleaned_json_block = clean_json_string(json_block)
    try:
        parsed = json.loads(cleaned_json_block)
    except json.JSONDecodeError as e:
        raise Exception(
            "LLM returned invalid JSON during extraction.\n"
            f"JSON error: {e}\n"
            f"Problematic JSON preview:\n{cleaned_json_block[:1500]}"
        )

    return normalize_root_fields(parsed, cleaned_text)