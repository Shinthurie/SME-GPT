"""
Phase 2 — Training Data Generator
===================================
Builds a fine-tuning dataset in Alpaca JSONL format from:
  1. Existing confirmed documents in the database (raw_text → extracted JSON pairs)
  2. Synthetic examples generated via the current LLM (DeepSeek or Ollama)

Output: backend/training_data/sme_gpt_train.jsonl
        backend/training_data/sme_gpt_eval.jsonl  (10% holdout)

Usage:
    python backend/scripts/generate_training_data.py
    python backend/scripts/generate_training_data.py --synthetic 50
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

_backend = Path(__file__).resolve().parent.parent
load_dotenv(_backend / ".env")
sys.path.insert(0, str(_backend))

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "")
OUTPUT_DIR = _backend / "training_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Prompt templates (same format used at inference time) ─────────────────────

EXTRACTION_SYSTEM = (
    "You are a financial document data extraction engine for Sri Lankan SME businesses. "
    "You output ONLY a single valid JSON object — no markdown fences, no explanation, "
    "no text before or after the JSON. Start your response with { and end with }."
)

EXTRACTION_USER_TEMPLATE = """\
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

TAX FIELDS: Only extract tax_amount / tax_rate if EXPLICITLY printed. Use "" if not shown.

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
{ocr_text}"""

CORRECTION_SYSTEM = (
    "You are an OCR text correction assistant for financial documents from Sri Lanka. "
    "You fix OCR errors in English text while preserving all Sinhala characters exactly as-is. "
    "You output ONLY the corrected text — no explanations, no commentary, nothing else."
)

CORRECTION_USER_TEMPLATE = """\
You are correcting OCR text from a financial document (invoice, receipt, or purchase order).

STRICT RULES:
- Fix OCR spelling mistakes in COMMON words only
- Do NOT correct company names, brand names, shop names, or proper nouns
- Preserve ALL numbers, prices, totals, dates, phone numbers, IDs exactly
- Preserve ALL Sinhala text exactly as-is
- Output ONLY the corrected text — no explanation, no commentary

Raw OCR text to correct:
{raw_text}"""


def load_records_from_db() -> list[dict]:
    """Fetch all confirmed records that have raw_text from the database."""
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL not set — skipping DB records.")
        return []

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        "documentId", "documentType", "orderId", "flowType",
                        "companyName", "supplierName", "docDate", "currency",
                        "rawTotalAmount", "finalTotalAmount", "payableAmount",
                        "cashReturn", "taxAmount", "taxRate",
                        "receivedStatus", "paidStatus", "rawText", "correctedText",
                        "status"
                    FROM "FinancialDocument"
                    WHERE "deletedAt" IS NULL
                      AND "rawText" IS NOT NULL
                      AND "rawText" != ''
                      AND "status" = 'confirmed'
                    ORDER BY "createdAt" DESC
                    """
                )
                return cur.fetchall() or []
    except Exception as e:
        print(f"WARNING: Could not load DB records: {e}")
        return []


def row_to_expected_json(row: dict) -> dict:
    """Convert a DB row to the expected extraction JSON output."""
    def maybe(v):
        return str(v) if v is not None else ""

    return {
        "document_id": maybe(row.get("documentId")),
        "document_type": maybe(row.get("documentType")) or "unknown",
        "order_id": maybe(row.get("orderId")),
        "flow_type": maybe(row.get("flowType")) or "unknown",
        "company_name": maybe(row.get("companyName")),
        "supplier_name": maybe(row.get("supplierName")),
        "date": maybe(row.get("docDate")),
        "currency": maybe(row.get("currency")) or "LKR",
        "raw_total_amount": str(row.get("rawTotalAmount") or ""),
        "final_total_amount": str(row.get("finalTotalAmount") or ""),
        "payable_amount": str(row.get("payableAmount") or ""),
        "cash_return": str(row.get("cashReturn") or ""),
        "tax_amount": str(row.get("taxAmount") or ""),
        "tax_rate": str(row.get("taxRate") or ""),
        "received_status": maybe(row.get("receivedStatus")),
        "paid_status": maybe(row.get("paidStatus")),
        "items": [],
    }


def make_extraction_example(ocr_text: str, expected_json: dict) -> dict:
    """Alpaca-format training example for extraction task."""
    return {
        "instruction": EXTRACTION_SYSTEM,
        "input": EXTRACTION_USER_TEMPLATE.format(ocr_text=ocr_text.strip()),
        "output": json.dumps(expected_json, ensure_ascii=False, indent=2),
    }


def make_correction_example(raw_text: str, corrected_text: str) -> dict:
    """Alpaca-format training example for OCR correction task."""
    return {
        "instruction": CORRECTION_SYSTEM,
        "input": CORRECTION_USER_TEMPLATE.format(raw_text=raw_text.strip()),
        "output": corrected_text.strip(),
    }


SYNTHETIC_TEMPLATES = [
    {
        "ocr": "INVOICE\nINVOICE NO: INV-2024-001\nDate: 15/01/2024\nBill To: ABC Company\nFrom: XYZ Suppliers\n\nItem         Qty  Price  Total\nA4 Paper      5   350    1750\nPen Set       3   200    600\n\nTotal: LKR 2350\nPayable: LKR 2350",
        "json": {
            "document_type": "invoice", "order_id": "INV-2024-001",
            "flow_type": "payable", "company_name": "XYZ Suppliers",
            "supplier_name": "ABC Company", "date": "15/01/2024",
            "currency": "LKR", "raw_total_amount": "2350",
            "final_total_amount": "2350", "payable_amount": "2350",
            "cash_return": "", "tax_amount": "", "tax_rate": "",
            "items": [
                {"description": "A4 Paper", "quantity": "5", "unit_price": "350", "line_total": "1750"},
                {"description": "Pen Set", "quantity": "3", "unit_price": "200", "line_total": "600"},
            ],
        },
    },
    {
        "ocr": "ලදුපත\nඅංකය: R-567\nදිනය: 20-02-2024\nගැනුම්කරු: Priya\nවිස්තරය    ප්‍රමාණය  මිල\nදිවුල්     2      150\nකෙසෙල්    4       80\nඑකතුව: රු 620",
        "json": {
            "document_type": "receipt", "order_id": "R-567",
            "flow_type": "expense", "company_name": "Customer",
            "supplier_name": "Priya", "date": "20-02-2024",
            "currency": "LKR", "raw_total_amount": "620",
            "final_total_amount": "620", "payable_amount": "620",
            "cash_return": "", "tax_amount": "", "tax_rate": "",
            "items": [
                {"description": "දිවුල්", "quantity": "2", "unit_price": "150", "line_total": "300"},
                {"description": "කෙසෙල්", "quantity": "4", "unit_price": "80", "line_total": "320"},
            ],
        },
    },
    {
        "ocr": "PURCHASE ORDER\nPO No: PO-2024-089\nDate: 10/03/2024\nTo: Colombo Office Supplies\nFrom: Tech Solutions Ltd\n\nDescription     Units  Unit Price  Amount\nLaptop Stand      2     1500       3000\nUSB Hub           5      800       4000\nSub Total: 7000\nVAT (18%): 1260\nTotal: LKR 8260",
        "json": {
            "document_type": "po", "order_id": "PO-2024-089",
            "flow_type": "payable", "company_name": "Colombo Office Supplies",
            "supplier_name": "Tech Solutions Ltd", "date": "10/03/2024",
            "currency": "LKR", "raw_total_amount": "8260",
            "final_total_amount": "8260", "payable_amount": "8260",
            "cash_return": "", "tax_amount": "1260", "tax_rate": "18",
            "items": [
                {"description": "Laptop Stand", "quantity": "2", "unit_price": "1500", "line_total": "3000"},
                {"description": "USB Hub", "quantity": "5", "unit_price": "800", "line_total": "4000"},
            ],
        },
    },
]


def build_dataset(n_synthetic: int = 20) -> list[dict]:
    examples = []

    # --- From database ---
    print("Loading records from database...")
    rows = load_records_from_db()
    print(f"  Found {len(rows)} confirmed records with raw text.")

    for row in rows:
        raw = str(row.get("rawText") or "").strip()
        corrected = str(row.get("correctedText") or "").strip()
        if not raw:
            continue
        expected = row_to_expected_json(row)
        examples.append(make_extraction_example(raw, expected))
        if corrected and corrected != raw:
            examples.append(make_correction_example(raw, corrected))

    # --- Built-in synthetic templates ---
    for t in SYNTHETIC_TEMPLATES:
        examples.append(make_extraction_example(t["ocr"], t["json"]))

    # --- Additional synthetic (duplicated with light variation) ---
    for i in range(n_synthetic):
        tmpl = random.choice(SYNTHETIC_TEMPLATES)
        ocr = tmpl["ocr"].replace("2024", f"202{random.randint(3,4)}")
        examples.append(make_extraction_example(ocr, tmpl["json"]))

    random.shuffle(examples)
    return examples


def save_dataset(examples: list[dict]):
    split = max(1, len(examples) // 10)
    eval_set = examples[:split]
    train_set = examples[split:]

    train_path = OUTPUT_DIR / "sme_gpt_train.jsonl"
    eval_path  = OUTPUT_DIR / "sme_gpt_eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for ex in train_set:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for ex in eval_set:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\nDataset saved:")
    print(f"  Train: {len(train_set)} examples -> {train_path}")
    print(f"  Eval:  {len(eval_set)} examples  -> {eval_path}")
    print(f"\nUpload these two files to Google Colab for Phase 3 fine-tuning.")
    return train_path, eval_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", type=int, default=20,
                        help="Number of extra synthetic examples to generate (default 20)")
    args = parser.parse_args()

    examples = build_dataset(n_synthetic=args.synthetic)
    print(f"\nTotal examples: {len(examples)}")
    save_dataset(examples)
