import json
import os
import re
import requests
from llm_correction import clean_ocr_text

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def call_ollama(prompt: str) -> str:
    url = f"{OLLAMA_HOST}/api/generate"

    try:
        response = requests.post(
            url,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0
                }
            },
            timeout=600
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError as e:
        raise Exception(
            f"Could not connect to Ollama at {OLLAMA_HOST}. "
            f"Please start Ollama and run the model first. Error: {e}"
        )
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Ollama HTTP error: {e}. Response: {response.text}")
    except requests.exceptions.Timeout:
        raise Exception("Ollama extraction request timed out.")


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
Return ONLY one valid JSON object.

Do not write explanations.
Do not write notes.
Do not write markdown.
Do not ask for more input.
Do not rewrite the OCR.

Use this exact structure:

{{
  "document_id": "",
  "document_type": "unknown",
  "order_id": "",
  "flow_type": "unknown",
  "company_name": "",
  "supplier_name": "",
  "date": "",
  "currency": "",
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
You are an extraction engine for OCR text from financial documents.

Return ONLY one valid JSON object.

STRICT RULES:
- Do NOT write explanations
- Do NOT write notes
- Do NOT rewrite the OCR
- Do NOT ask for more text
- Copy values exactly from OCR
- Preserve Sinhala text in Sinhala script
- Do NOT translate Sinhala to English
- Do NOT transliterate Sinhala into English letters
- Do NOT calculate new numbers
- Do NOT invent missing values
- Use empty string "" for missing values

DOCUMENT TYPE RULES:
- "invoice" if the text clearly says invoice
- "receipt" for shop bills, salon bills, cash bills, or short retail receipts
- "po" for purchase orders
- "dn" for delivery notes
- otherwise "unknown"

FLOW TYPE RULES:
- "expense" for salon/shop/service purchase receipts paid by the business/customer
- "income" if it is clearly money received by the business
- otherwise "unknown" unless clearly payable/receivable

LAYOUT RULES:
- Top lines usually contain business/shop name
- Header area often contains phone number, date, and order id
- Middle lines often contain numbered item rows
- Bottom area usually contains total and cash return
- If only one total is visible, use it for raw_total_amount, final_total_amount, and payable_amount
- If cash return is visible, copy it exactly
- Extract visible item rows only
- Preserve item row order

Return JSON in exactly this structure:

{{
  "document_id": "",
  "document_type": "unknown",
  "order_id": "",
  "flow_type": "unknown",
  "company_name": "",
  "supplier_name": "",
  "date": "",
  "currency": "",
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