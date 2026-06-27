import json
import os
import re
from llm_correction import clean_ocr_text
from llm_client import call_llm

_EXTRACTION_SYSTEM = (
    "You are a financial document data extraction engine for Sri Lankan SME businesses. "
    "You output ONLY a single valid JSON object — no markdown fences, no explanation, "
    "no text before or after the JSON. Start your response with { and end with }."
)


def call_ollama(prompt: str) -> str:
    """Routes extraction calls to local Ollama.

    Uses Ollama's JSON output mode (format="json") so the model is constrained
    to emit a single valid JSON object. This eliminates most of the conversational
    preamble / markdown-fence noise that the regex scraping in extract_json_block()
    previously had to recover from, reducing JSON parse failures (IT-28).
    """
    return call_llm(prompt, system=_EXTRACTION_SYSTEM, format="json")


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

    # OCR receipt fix: ".300" on receipt totals is often a broken OCR read of "1300".
    # Only applies to exact 3-digit decimal strings (e.g. ".300", ".500").
    if re.fullmatch(r"\.\d{3}", text):
        corrected = int("1" + text[1:])
        print(f"[normalize_ocr_money] OCR receipt fix applied: {text!r} → {corrected}", flush=True)
        return corrected

    try:
        return float(text) if "." in text else int(text)
    except Exception as e:
        print(f"[normalize_ocr_money] parse error for value={value!r}: {e}", flush=True)
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
    except Exception as e:
        print(f"[normalize_number] parse error for value={value!r}: {e}", flush=True)
        return "NULL"


def detect_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"

    has_sinhala = bool(re.search(r"[඀-෿]", text))
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

    # If first 2-3 top lines look like a stacked business name, join them
    if len(top_lines) >= 2:
        joined = " ".join(top_lines[:2]).strip()
        if joined:
            return joined

    return current_company if current_company else "Customer"

def normalize_supplier_name(value: str, flow_type: str = "", document_type: str = "") -> str:
    text = str(value or "").strip()
    if not text or text.upper() == "NULL" or text.lower() in ("unknown", ""):
        # Smart default based on context
        if document_type in ("po", "dn") or flow_type in ("payable", "cash_outflow"):
            return "Supplier"
        if flow_type in ("receivable", "cash_inflow"):
            return "Customer"
        return "Supplier"
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

    flow_type = str(parsed.get("flow_type", "unknown")).strip().lower().replace(" ", "_") or "unknown"
    # Normalise legacy / misspelled values
    _flow_aliases = {
        "expense": "cash_outflow", "expence": "cash_outflow",
        "income": "cash_inflow", "revenue": "cash_inflow",
        "cash outflow": "cash_outflow", "cash inflow": "cash_inflow",
    }
    flow_type = _flow_aliases.get(flow_type, flow_type)

    # DN — delivery notes have no financial value; zero all amounts and lock flow
    if document_type == "dn":
        flow_type = "expense"          # stored for DB consistency, hidden in UI
        parsed["raw_total_amount"]  = ""
        parsed["final_total_amount"] = ""
        parsed["payable_amount"]    = ""
        parsed["cash_return"]       = ""
        parsed["paid_status"]       = "NULL"
        # Strip prices from items — only description + qty matter on a DN
        for item in parsed.get("items", []):
            item["unit_price"] = ""
            item["line_total"] = ""

    # PO — always payable; no cash return, no received status
    if document_type == "po":
        flow_type = "payable"
        parsed["cash_return"]       = ""
        parsed["received_status"]   = "NULL"

    # ── Auto-set paid/received status from flow_type ──────────────────────────
    # These express what has already happened at the time of the document.
    # Payable/receivable are OUTSTANDING — their status is set when settled later.
    _status_map = {
        "cash_outflow": ("NULL",         "paid"),
        "cash_inflow":  ("received",     "NULL"),
        "payable":      ("NULL",         "not_paid"),
        "receivable":   ("not_received", "NULL"),
        "expense":      ("NULL",         "paid"),   # DN uses expense
    }
    if flow_type in _status_map and document_type != "dn":  # DN already handled above
        _rec, _paid = _status_map[flow_type]
        parsed.setdefault("received_status", _rec)
        parsed.setdefault("paid_status",     _paid)
        # Override only if the LLM returned empty/NULL
        if str(parsed.get("received_status", "")).strip() in ("", "NULL", "null"):
            parsed["received_status"] = _rec
        if str(parsed.get("paid_status", "")).strip() in ("", "NULL", "null"):
            parsed["paid_status"] = _paid

    # ── Default date to today if missing ─────────────────────────────────────
    from datetime import date as _today
    _date_val = str(parsed.get("date", "")).strip()
    if not _date_val or _date_val.upper() in ("", "NULL", "NONE"):
        parsed["date"] = _today.today().strftime("%d/%m/%Y")

    # ── Extracted company name from document ─────────────────────────────────
    # company_name from OCR = the ISSUING company on the document.
    # In /confirm-save this will be overridden with the user's registered company.
    # supplier_name = the OTHER party.
    # If supplier_name is empty but company_name was extracted, move company_name
    # to supplier_name (it's the OTHER party's name the document was issued by).
    _ocr_company  = infer_company_name_from_text(source_text, str(parsed.get("company_name", "")).strip())
    _ocr_supplier = str(parsed.get("supplier_name", "")).strip()

    if not _ocr_supplier or _ocr_supplier.upper() in ("NULL", "NONE"):
        # Use the extracted company name as the OTHER party's name
        _ocr_supplier = _ocr_company if _ocr_company else ""

    _supplier_final = normalize_supplier_name(_ocr_supplier, flow_type, document_type)

    return {
        "document_id": str(parsed.get("document_id", "")).strip(),
        "document_type": document_type,
        "order_id": str(parsed.get("order_id", "")).strip(),
        "flow_type": flow_type,
        "company_name": _ocr_company,   # will be overridden in /confirm-save with user's company
        "supplier_name": _supplier_final,
        "date": str(parsed.get("date", "")).strip(),
        "currency": str(parsed.get("currency", "")).strip(),
        "raw_total_amount": normalize_ocr_money(parsed.get("raw_total_amount")),
        "final_total_amount": normalize_ocr_money(parsed.get("final_total_amount")),
        "payable_amount": normalize_ocr_money(parsed.get("payable_amount")),
        "cash_return": normalize_number(parsed.get("cash_return")),
        "tax_amount": normalize_ocr_money(parsed.get("tax_amount")) if parsed.get("tax_amount") not in (None, "", "NULL") else "NULL",
        "tax_rate": normalize_number(parsed.get("tax_rate")) if parsed.get("tax_rate") not in (None, "", "NULL") else "NULL",
        "received_status": str(parsed.get("received_status", "")).strip(),
        "paid_status": str(parsed.get("paid_status", "")).strip(),
        "language": language,
        "items": normalize_items(parsed.get("items", [])),
        # Iteration 10 — PO/DN workflow fields
        "due_date": str(parsed.get("due_date", "")).strip(),
        "delivery_date": str(parsed.get("delivery_date", "")).strip(),
        "approved_by": str(parsed.get("approved_by", "")).strip(),
        "proof_of_delivery": parsed.get("proof_of_delivery", None),
        "signed": parsed.get("signed", None),
        # Iteration 11 — contact/location fields
        "supplier_city": str(parsed.get("supplier_city", "")).strip(),
        "supplier_phone": str(parsed.get("supplier_phone", "")).strip(),
        "supplier_email": str(parsed.get("supplier_email", "")).strip(),
        "company_city": str(parsed.get("company_city", "")).strip(),
        "company_phone": str(parsed.get("company_phone", "")).strip(),
        "company_email": str(parsed.get("company_email", "")).strip(),
    }

def retry_extract_json_only(raw_text: str) -> str:
    retry_prompt = f"""
Return ONLY one valid JSON object — no markdown, no explanations, no notes.

Extract ALL line items. For each item row extract:
- description (item name)
- quantity (Qty/QTY/Nos/Pcs/Units/ป๊รมาณย)
- unit_price (Rate/Price/Unit Rate/Unit Price/อาคมิล)
- line_total (Amount/Total/รู.)

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
  "tax_amount": "",
  "tax_rate": "",
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
- "payable"      → we owe money to a supplier, not yet paid (we are the buyer)
- "receivable"   → a customer owes us money, not yet received (we are the seller)
- "cash_outflow" → already paid retail bill / cash purchase / expense paid
- "cash_inflow"  → money already received from a customer / income received
- "unknown"      → when unclear

FIELD EXTRACTION GUIDE:
- company_name: the business whose name appears at the TOP of this document — the ISSUER
  (e.g. the shop that issued the receipt, the company that wrote the invoice)
- supplier_name: the OTHER party — the buyer, customer, recipient, or counter-party.
  This is NOT the issuing company. It is whoever is on the other side of the transaction.
  Examples: for a shop receipt → the customer who paid; for an invoice → the client being billed;
  for a PO → the supplier being ordered from. Leave empty if only one company name appears.
- order_id: any invoice number, receipt number, PO number, bill number, reference number
- date: the document date in any format found. If no date is visible, use today's date.

LINE ITEMS — THIS IS CRITICAL:
Each item row in the document must be a separate object in "items".
For EACH item look for these columns (they may use different labels):
  - description: item name/product/service (required — always extract)
  - quantity: amount/count (also labeled as: Qty, QTY, Nos, No., Pcs, Units, Count, ป๊รมาณย)
  - unit_price: price per unit (also labeled as: Rate, Unit Rate, Price, U/Price, Unit Price, อาคมิล, มิล)
  - line_total: row total / amount (also labeled as: Amount, Total, Line Total, Sub, รู.)
If a column is missing from a row, use "" — do NOT skip the item row entirely.
For receipts with no explicit qty column: assume quantity = 1 if only price and total are given.
Extract ALL item rows visible in the document — do not skip any.

AMOUNT FIELDS:
- raw_total_amount: the grand total as it appears in the OCR
- final_total_amount: same as raw_total_amount unless a discount is applied
- payable_amount: amount the buyer must pay (after discount, if any)
- cash_return: change given back to customer (if shown)
- currency: LKR, USD, EUR etc. (default LKR if not stated)

TAX FIELDS (CRITICAL — only extract if explicitly shown on the document):
- tax_amount: the actual tax amount printed on the document (e.g. "VAT: 300.00", "Tax: 45.00"). Use "" if no tax is shown.
- tax_rate: the tax percentage printed on the document (e.g. 15 for "VAT 15%", 8 for "GST 8%"). Use "" if no rate is shown.
- Do NOT calculate or guess tax. Only extract what is EXPLICITLY printed.

WORKFLOW FIELDS (Iteration 10 — only extract if explicitly shown):
- due_date: payment due date if printed on the document (e.g. "Due: 30/07/2025"). Use "" if not shown.
- delivery_date: expected delivery date if printed (e.g. "Delivery by: 15/07/2025"). Use "" if not shown.
- approved_by: name of person who approved the document (e.g. "Approved by: John Silva"). Use "" if not shown.
- proof_of_delivery: true if document has a "Received By" signature section, false otherwise. Use null if unknown.
- signed: true if there is a signature on the document, false if signature field is blank. Use null if unknown.

CONTACT FIELDS (Iteration 11 — extract if visible on the document):
- supplier_city: city or town of the supplier/other-party (e.g. "Colombo", "Kandy", "Galle"). Use "" if not visible.
- supplier_phone: phone/mobile number of the supplier/other-party. Use "" if not visible.
- supplier_email: email address of the supplier/other-party. Use "" if not visible.
- company_city: city or town of the issuing company (top of document). Use "" if not visible.
- company_phone: phone/mobile of the issuing company. Use "" if not visible.
- company_email: email of the issuing company. Use "" if not visible.
Note: For city, look for labels like "City:", "Address:", location text under company names, or any visible address line.

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
  "tax_amount": "",
  "tax_rate": "",
  "received_status": "",
  "paid_status": "",
  "due_date": "",
  "delivery_date": "",
  "approved_by": "",
  "proof_of_delivery": null,
  "signed": null,
  "supplier_city": "",
  "supplier_phone": "",
  "supplier_email": "",
  "company_city": "",
  "company_phone": "",
  "company_email": "",
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
