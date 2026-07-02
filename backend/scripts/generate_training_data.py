"""
Training Data Generator — Gemini Fine-Tuning Format
=====================================================
Builds four JSONL files in Gemini supervised fine-tuning format from:
  1. Confirmed documents in the Postgres database
  2. Built-in synthetic examples covering all Sri Lankan document types

Output files (backend/training_data/):
  gemini_extraction.jsonl  — OCR text  → extracted JSON fields
  gemini_correction.jsonl  — noisy OCR → clean corrected text
  gemini_planning.jsonl    — NL query  → PAL execution plan (JSON)
  gemini_answering.jsonl   — plan+data → human-readable answer (EN + Sinhala)

These files are uploaded to Google Cloud Storage and used with Vertex AI
supervised tuning for gemini-2.5-flash (see scripts/vertex_ai_finetune.sh).

Usage:
    cd backend
    python scripts/generate_training_data.py
    python scripts/generate_training_data.py --synthetic 50 --qa 100
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

_backend = Path(__file__).resolve().parent.parent
load_dotenv(_backend / ".env")
sys.path.insert(0, str(_backend))

DATABASE_URL = os.getenv("DATABASE_URL", "")
OUTPUT_DIR = _backend / "training_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Gemini fine-tuning format helper ──────────────────────────────────────────

def _example(system: str, user: str, model: str) -> dict:
    """One supervised fine-tuning example in Gemini conversation format."""
    return {
        "systemInstruction": {
            "role": "system",
            "parts": [{"text": system}],
        },
        "contents": [
            {"role": "user",  "parts": [{"text": user}]},
            {"role": "model", "parts": [{"text": model}]},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — FIELD EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM = (
    "You are a financial document data extraction engine for Sri Lankan SME businesses. "
    "You output ONLY a single valid JSON object — no markdown fences, no explanation, "
    "no text before or after the JSON. Start your response with { and end with }."
)

_EXTRACTION_USER_TEMPLATE = """\
Extract structured data from this financial document OCR text.

STRICT RULES:
- Copy values EXACTLY from the OCR text
- Preserve ALL Sinhala characters in Sinhala Unicode script — do NOT translate or transliterate
- Do NOT calculate or invent numbers
- Use "" for any field not found in the text
- document_type: "invoice" | "receipt" | "po" | "dn" | "unknown"
- flow_type: "payable" (we owe supplier) | "receivable" (customer owes us) | "expense" (cash purchase) | "income" (cash received) | "unknown"

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
    {{"description": "", "quantity": "", "unit_price": "", "line_total": ""}}
  ]
}}

OCR text:
{ocr_text}"""


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — OCR CORRECTION
# ─────────────────────────────────────────────────────────────────────────────

_CORRECTION_SYSTEM = (
    "You are an OCR text correction assistant for financial documents from Sri Lanka. "
    "You fix OCR errors in English text while preserving all Sinhala characters exactly as-is. "
    "You output ONLY the corrected text — no explanations, no commentary, nothing else."
)

_CORRECTION_USER_TEMPLATE = """\
Correct OCR errors in this financial document text.

STRICT RULES:
- Fix OCR spelling mistakes in COMMON words only (toatl→total, invioce→invoice)
- Do NOT correct company names, brand names, shop names, or proper nouns
- Preserve ALL numbers, prices, totals, dates, phone numbers, IDs exactly as-is
- Preserve ALL Sinhala text exactly as-is — never translate or transliterate
- Output ONLY the corrected text — no explanation, no commentary

Raw OCR text:
{raw_text}"""


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — PAL PLANNING
# ─────────────────────────────────────────────────────────────────────────────

_PLANNING_SYSTEM = (
    "You are a financial query planner for a Sri Lankan SME system. "
    "You convert natural-language questions into strict JSON execution plans. "
    "You never compute results yourself — you only describe what to compute. "
    "You must return ONLY valid JSON, no prose, no markdown."
)

_PLANNING_USER_TEMPLATE = """\
Convert this financial question into a JSON execution plan.

Allowed tasks: aggregate_sum, aggregate_avg, aggregate_count, compare, lookup_value, group_by_sum
Allowed filter ops: eq, in, contains, gte, lte, between
Canonical fields: item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor, flow_type
flow_type values: payable, receivable, cash_inflow, cash_outflow
revenue/income → flow_type in [receivable, cash_inflow]
expense/cost   → flow_type in [payable, cash_outflow]
Sinhala equivalents: "ගෙවිය යුතු"=payable, "ලැබිය යුතු"=receivable, "මේ මාසේ"=this month, "ගිය මාසේ"=last month

Return ONLY valid JSON in this shape:
{{"task": "aggregate_sum", "filters": [{{"field": "flow_type", "op": "eq", "value": "payable"}}], "measure": {{"field": "total", "agg": "sum"}}, "group_by": [], "output": {{"format": "currency"}}}}

Question: {question}
{retry_note}"""


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — BILINGUAL ANSWER GENERATION
# ─────────────────────────────────────────────────────────────────────────────

_ANSWERING_SYSTEM = (
    "You are a financial assistant for Sri Lankan SME businesses. "
    "You answer in {language} using ONLY the numbers provided. "
    "You never invent or adjust numbers. "
    "Return ONLY valid JSON: {{\"short_answer\": \"\", \"full_answer\": \"\"}}."
)

_ANSWERING_USER_TEMPLATE = """\
Answer this financial question in {language}.

Rules:
- Use ONLY the numbers in the Computed Result
- short_answer: one business-friendly sentence
- full_answer: adds brief context (currency, document count)
- Format LKR amounts with commas: LKR 1,250,000.00
- Return ONLY valid JSON: {{"short_answer": "", "full_answer": ""}}

Company: {company_name}
Question: {question}
Computed Result:
{computed_json}"""


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DOCUMENT EXAMPLES
# ─────────────────────────────────────────────────────────────────────────────

_SYNTHETIC_DOCS = [
    {
        "ocr": "INVOICE\nINVOICE NO: INV-2025-001\nDate: 15/01/2025\nBill To: AIESEC Sri Lanka\nFrom: XYZ Office Supplies\n\nItem         Qty  Unit Price  Total\nA4 Paper      5   350         1750\nPen Set       3   200         600\nFile Folders  10  120         1200\n\nSubtotal: LKR 3550\nVAT (18%): LKR 639\nTotal: LKR 4189\nPayable: LKR 4189",
        "corrected": "INVOICE\nINVOICE NO: INV-2025-001\nDate: 15/01/2025\nBill To: AIESEC Sri Lanka\nFrom: XYZ Office Supplies\n\nItem         Qty  Unit Price  Total\nA4 Paper      5   350         1750\nPen Set       3   200         600\nFile Folders  10  120         1200\n\nSubtotal: LKR 3550\nVAT (18%): LKR 639\nTotal: LKR 4189\nPayable: LKR 4189",
        "json": {
            "document_type": "invoice", "order_id": "INV-2025-001",
            "flow_type": "payable", "company_name": "AIESEC Sri Lanka",
            "supplier_name": "XYZ Office Supplies", "date": "15/01/2025",
            "currency": "LKR", "raw_total_amount": "4189",
            "final_total_amount": "4189", "payable_amount": "4189",
            "cash_return": "", "tax_amount": "639", "tax_rate": "18",
            "received_status": "", "paid_status": "not_paid",
            "items": [
                {"description": "A4 Paper", "quantity": "5", "unit_price": "350", "line_total": "1750"},
                {"description": "Pen Set", "quantity": "3", "unit_price": "200", "line_total": "600"},
                {"description": "File Folders", "quantity": "10", "unit_price": "120", "line_total": "1200"},
            ],
        },
    },
    {
        "ocr": "ලදුපත\nඅංකය: R-2025-567\nදිනය: 20-02-2025\nවෙළෙදසැල: ශ්‍රී රාජ සුපර්\nගැනුම්කරු: Priya\n\nවිස්තරය      ප්‍රමාණය  මිල    එකතුව\nදිවුල්        2        150    300\nකෙසෙල්       4        80     320\nඅඹ            3        200    600\n\nඑකතුව: රු 1220\nලැබූ මුදල: රු 1500\nකෙරුම: රු 280",
        "corrected": "ලදුපත\nඅංකය: R-2025-567\nදිනය: 20-02-2025\nවෙළෙදසැල: ශ්‍රී රාජ සුපර්\nගැනුම්කරු: Priya\n\nවිස්තරය      ප්‍රමාණය  මිල    එකතුව\nදිවුල්        2        150    300\nකෙසෙල්       4        80     320\nඅඹ            3        200    600\n\nඑකතුව: රු 1220\nලැබූ මුදල: රු 1500\nකෙරුම: රු 280",
        "json": {
            "document_type": "receipt", "order_id": "R-2025-567",
            "flow_type": "expense", "company_name": "ශ්‍රී රාජ සුපර්",
            "supplier_name": "ශ්‍රී රාජ සුපර්", "date": "20-02-2025",
            "currency": "LKR", "raw_total_amount": "1220",
            "final_total_amount": "1220", "payable_amount": "1220",
            "cash_return": "280", "tax_amount": "", "tax_rate": "",
            "received_status": "", "paid_status": "",
            "items": [
                {"description": "දිවුල්", "quantity": "2", "unit_price": "150", "line_total": "300"},
                {"description": "කෙසෙල්", "quantity": "4", "unit_price": "80", "line_total": "320"},
                {"description": "අඹ", "quantity": "3", "unit_price": "200", "line_total": "600"},
            ],
        },
    },
    {
        "ocr": "PURCHASE ORDER\nPO No: PO-2025-089\nDate: 10/03/2025\nTo: Colombo Office Supplies (Pvt) Ltd\nFrom: Tech Solutions Lanka\n\nDescription        Units  Unit Price  Amount\nLaptop Stand          2     1500       3000\nUSB Hub               5      800       4000\nWireless Mouse        3     2500       7500\n\nSub Total: 14500\nVAT (18%): 2610\nTotal: LKR 17110",
        "corrected": "PURCHASE ORDER\nPO No: PO-2025-089\nDate: 10/03/2025\nTo: Colombo Office Supplies (Pvt) Ltd\nFrom: Tech Solutions Lanka\n\nDescription        Units  Unit Price  Amount\nLaptop Stand          2     1500       3000\nUSB Hub               5      800       4000\nWireless Mouse        3     2500       7500\n\nSub Total: 14500\nVAT (18%): 2610\nTotal: LKR 17110",
        "json": {
            "document_type": "po", "order_id": "PO-2025-089",
            "flow_type": "payable", "company_name": "Tech Solutions Lanka",
            "supplier_name": "Colombo Office Supplies (Pvt) Ltd", "date": "10/03/2025",
            "currency": "LKR", "raw_total_amount": "17110",
            "final_total_amount": "17110", "payable_amount": "17110",
            "cash_return": "", "tax_amount": "2610", "tax_rate": "18",
            "received_status": "", "paid_status": "not_paid",
            "items": [
                {"description": "Laptop Stand", "quantity": "2", "unit_price": "1500", "line_total": "3000"},
                {"description": "USB Hub", "quantity": "5", "unit_price": "800", "line_total": "4000"},
                {"description": "Wireless Mouse", "quantity": "3", "unit_price": "2500", "line_total": "7500"},
            ],
        },
    },
    {
        "ocr": "INVOICE\nInvoice No: INV-2025-042\nDate: 05/04/2025\nClient: Virtusa (Pvt) Ltd\nIssued by: AIESEC Sri Lanka\n\nService Description         Hours  Rate/hr   Amount\nTraining Workshop              8    5000      40000\nFacilitation Services          4    7500      30000\n\nTotal: LKR 70000\nPayment Due: 30/04/2025",
        "corrected": "INVOICE\nInvoice No: INV-2025-042\nDate: 05/04/2025\nClient: Virtusa (Pvt) Ltd\nIssued by: AIESEC Sri Lanka\n\nService Description         Hours  Rate/hr   Amount\nTraining Workshop              8    5000      40000\nFacilitation Services          4    7500      30000\n\nTotal: LKR 70000\nPayment Due: 30/04/2025",
        "json": {
            "document_type": "invoice", "order_id": "INV-2025-042",
            "flow_type": "receivable", "company_name": "AIESEC Sri Lanka",
            "supplier_name": "Virtusa (Pvt) Ltd", "date": "05/04/2025",
            "currency": "LKR", "raw_total_amount": "70000",
            "final_total_amount": "70000", "payable_amount": "70000",
            "cash_return": "", "tax_amount": "", "tax_rate": "",
            "received_status": "not_received", "paid_status": "",
            "items": [
                {"description": "Training Workshop", "quantity": "8", "unit_price": "5000", "line_total": "40000"},
                {"description": "Facilitation Services", "quantity": "4", "unit_price": "7500", "line_total": "30000"},
            ],
        },
    },
    {
        "ocr": "INVIOCE\nInvoce No: IN-098\nDdate: 12/05/2025\nBill to: ABC Compnay\nFrom: Suppiler XYZ\n\nIetm      Qty  Pirce  Toatl\nPapre     10   200    2000\nPne set    5   150     750\n\nToatl Amunt: LKR 2750",
        "corrected": "INVOICE\nInvoice No: IN-098\nDate: 12/05/2025\nBill to: ABC Company\nFrom: Supplier XYZ\n\nItem      Qty  Price  Total\nPaper     10   200    2000\nPen set    5   150     750\n\nTotal Amount: LKR 2750",
        "json": {
            "document_type": "invoice", "order_id": "IN-098",
            "flow_type": "payable", "company_name": "ABC Company",
            "supplier_name": "Supplier XYZ", "date": "12/05/2025",
            "currency": "LKR", "raw_total_amount": "2750",
            "final_total_amount": "2750", "payable_amount": "2750",
            "cash_return": "", "tax_amount": "", "tax_rate": "",
            "received_status": "", "paid_status": "not_paid",
            "items": [
                {"description": "Paper", "quantity": "10", "unit_price": "200", "line_total": "2000"},
                {"description": "Pen set", "quantity": "5", "unit_price": "150", "line_total": "750"},
            ],
        },
    },
    {
        "ocr": "DELIVERY NOTE\nDN No: DN-2025-034\nDate: 18/06/2025\nDelivered to: AIESEC Regional Office\nFrom: Classic Printers\n\nItem                  Qty\nPrinted Brochures     500\nBanner 6x4ft            2\nFlyers A5            1000\n\nDelivery Status: Delivered\nSigned by: K. Perera",
        "corrected": "DELIVERY NOTE\nDN No: DN-2025-034\nDate: 18/06/2025\nDelivered to: AIESEC Regional Office\nFrom: Classic Printers\n\nItem                  Qty\nPrinted Brochures     500\nBanner 6x4ft            2\nFlyers A5            1000\n\nDelivery Status: Delivered\nSigned by: K. Perera",
        "json": {
            "document_type": "dn", "order_id": "DN-2025-034",
            "flow_type": "expense", "company_name": "AIESEC Regional Office",
            "supplier_name": "Classic Printers", "date": "18/06/2025",
            "currency": "LKR", "raw_total_amount": "",
            "final_total_amount": "", "payable_amount": "",
            "cash_return": "", "tax_amount": "", "tax_rate": "",
            "received_status": "received", "paid_status": "",
            "items": [
                {"description": "Printed Brochures", "quantity": "500", "unit_price": "", "line_total": ""},
                {"description": "Banner 6x4ft", "quantity": "2", "unit_price": "", "line_total": ""},
                {"description": "Flyers A5", "quantity": "1000", "unit_price": "", "line_total": ""},
            ],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC Q&A PAIRS (PAL planning + Bilingual answering)
# ─────────────────────────────────────────────────────────────────────────────

today = date.today()
_this_month_start = today.replace(day=1).isoformat()
_last_month_end   = (today.replace(day=1) - timedelta(days=1))
_last_month_start = _last_month_end.replace(day=1).isoformat()
_last_month_end   = _last_month_end.isoformat()
_this_year_start  = today.replace(month=1, day=1).isoformat()

_QA_PAIRS: list[dict] = [
    # ── Income queries ──
    {
        "question": "How much income did we earn last month?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_last_month_start, _last_month_end]},
            {"field": "flow_type", "op": "in", "value": ["receivable", "cash_inflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 125000.00, "currency": "LKR", "row_count": 3, "operation": "aggregate_sum"},
        "answer_en": {"short_answer": "AIESEC Sri Lanka earned LKR 125,000.00 in income last month.", "full_answer": "Total income (receivable and cash inflow) for AIESEC Sri Lanka last month was LKR 125,000.00 across 3 documents."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාව ගිය මාසේ LKR 125,000.00 ක ආදායමක් ඉපැයීය.", "full_answer": "AIESEC ශ්‍රී ලංකාවේ ගිය මාසය සඳහා සම්පූර්ණ ආදායම (ලැබිය යුතු සහ මුදල් ගලා ඒම) LKR 125,000.00 ක් වූ අතර, ලේඛන 3 ක් ඊට ඇතුළත් විය."},
    },
    {
        "question": "ගිය මාසේ ආදායම කීයද?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_last_month_start, _last_month_end]},
            {"field": "flow_type", "op": "in", "value": ["receivable", "cash_inflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 85000.00, "currency": "LKR", "row_count": 2, "operation": "aggregate_sum"},
        "answer_si": {"short_answer": "ගිය මාසේ AIESEC ශ්‍රී ලංකාවේ ආදායම LKR 85,000.00 කි.", "full_answer": "ගිය මාසය සඳහා AIESEC ශ්‍රී ලංකාවේ සම්පූර්ණ ආදායම LKR 85,000.00 ක් වූ අතර ලේඛන 2 ක් ඊට ඇතුළත් විය."},
        "answer_en": {"short_answer": "Income for AIESEC Sri Lanka last month was LKR 85,000.00.", "full_answer": "Total income last month for AIESEC Sri Lanka was LKR 85,000.00 across 2 documents."},
    },
    {
        "question": "What is our total revenue this year?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_this_year_start, today.isoformat()]},
            {"field": "flow_type", "op": "in", "value": ["receivable", "cash_inflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 1250000.00, "currency": "LKR", "row_count": 18, "operation": "aggregate_sum"},
        "answer_en": {"short_answer": "AIESEC Sri Lanka's total revenue this year is LKR 1,250,000.00.", "full_answer": "Total revenue (receivable and cash inflow) for AIESEC Sri Lanka this year is LKR 1,250,000.00 across 18 documents."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම වසරේ සම්පූර්ණ ආදායම LKR 1,250,000.00 කි.", "full_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම වසර සඳහා සම්පූර්ණ ආදායම LKR 1,250,000.00 ක් වූ අතර ලේඛන 18 ක් ඊට ඇතුළත් විය."},
    },
    # ── Expense queries ──
    {
        "question": "How much did we spend this month?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_this_month_start, today.isoformat()]},
            {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 47500.00, "currency": "LKR", "row_count": 5, "operation": "aggregate_sum"},
        "answer_en": {"short_answer": "AIESEC Sri Lanka spent LKR 47,500.00 this month.", "full_answer": "Total expenses (payable and cash outflow) for AIESEC Sri Lanka this month is LKR 47,500.00 across 5 documents."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාව මෙම මාසයේ LKR 47,500.00 ක් වියදම් කළේය.", "full_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම මාසය සඳහා සම්පූර්ණ වියදම් (ගෙවිය යුතු සහ මුදල් ගලා යෑම) LKR 47,500.00 ක් වූ අතර ලේඛන 5 ක් ඊට ඇතුළත් විය."},
    },
    {
        "question": "මේ මාසේ වියදම් කීයද?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_this_month_start, today.isoformat()]},
            {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 62000.00, "currency": "LKR", "row_count": 4, "operation": "aggregate_sum"},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාව මෙම මාසයේ LKR 62,000.00 ක් වියදම් කළේය.", "full_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම මාසය සඳහා සම්පූර්ණ වියදම් LKR 62,000.00 ක් (ලේඛන 4) විය."},
        "answer_en": {"short_answer": "AIESEC Sri Lanka spent LKR 62,000.00 this month.", "full_answer": "Total expenses for AIESEC Sri Lanka this month is LKR 62,000.00 across 4 documents."},
    },
    # ── Comparison queries ──
    {
        "question": "Compare spending this month vs last month",
        "plan": {"task": "compare", "compare_filters": [
            [{"field": "doc_date", "op": "between", "value": [_this_month_start, today.isoformat()]},
             {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]}],
            [{"field": "doc_date", "op": "between", "value": [_last_month_start, _last_month_end]},
             {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]}],
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": [47500.00, 63000.00], "currency": "LKR", "row_count": 9, "operation": "compare"},
        "answer_en": {"short_answer": "Spending this month (LKR 47,500.00) is lower than last month (LKR 63,000.00).", "full_answer": "For AIESEC Sri Lanka, total expenses this month are LKR 47,500.00 compared to LKR 63,000.00 last month — a decrease of LKR 15,500.00 (24.6%)."},
        "answer_si": {"short_answer": "මෙම මාසයේ වියදම් (LKR 47,500.00) ගිය මාසයට (LKR 63,000.00) වඩා අඩුය.", "full_answer": "AIESEC ශ්‍රී ලංකාව සඳහා, මෙම මාසයේ සම්පූර්ණ වියදම් LKR 47,500.00 ක් වන අතර ගිය මාසයේ LKR 63,000.00 ක් විය — LKR 15,500.00 (24.6%) අඩුවීමකි."},
    },
    # ── Group by ──
    {
        "question": "Monthly income breakdown for this year",
        "plan": {"task": "group_by_sum", "filters": [
            {"field": "doc_date", "op": "between", "value": [_this_year_start, today.isoformat()]},
            {"field": "flow_type", "op": "in", "value": ["receivable", "cash_inflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": ["doc_date"], "output": {"format": "currency"}},
        "computed": {"value": 1250000.00, "currency": "LKR", "row_count": 18, "operation": "group_by_sum"},
        "answer_en": {"short_answer": "Monthly income breakdown for AIESEC Sri Lanka this year totals LKR 1,250,000.00.", "full_answer": "Total income for AIESEC Sri Lanka this year is LKR 1,250,000.00 across 18 documents, broken down by month."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම වසරේ මාසික ආදායම් සාරාංශය LKR 1,250,000.00 කි.", "full_answer": "AIESEC ශ්‍රී ලංකාව සඳහා මෙම වසරේ සම්පූර්ණ ආදායම ලේඛන 18 ක් හරහා LKR 1,250,000.00 ක් වූ අතර, මාසික වශයෙන් කඩා දක්වා ඇත."},
    },
    {
        "question": "Top 3 suppliers by total spend",
        "plan": {"task": "group_by_sum", "filters": [
            {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": ["vendor"], "output": {"format": "currency"}},
        "computed": {"value": 245000.00, "currency": "LKR", "row_count": 12, "operation": "group_by_sum"},
        "answer_en": {"short_answer": "Top 3 suppliers for AIESEC Sri Lanka account for LKR 245,000.00 in total spend.", "full_answer": "The top 3 suppliers by total spend for AIESEC Sri Lanka total LKR 245,000.00 across 12 documents."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාවේ ඉහළ සැපයුම්කරුවන් 3 දෙනාගේ සම්පූර්ණ වියදම LKR 245,000.00 කි.", "full_answer": "AIESEC ශ්‍රී ලංකාව සඳහා ඉහළ ම සැපයුම්කරුවන් 3 දෙනාගේ සම්පූර්ණ වියදම LKR 245,000.00 ක් (ලේඛන 12) විය."},
    },
    # ── Supplier/vendor filter ──
    {
        "question": "How much do we owe Virtusa?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]},
            {"field": "vendor", "op": "contains", "value": "Virtusa"},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 175000.00, "currency": "LKR", "row_count": 2, "operation": "aggregate_sum"},
        "answer_en": {"short_answer": "AIESEC Sri Lanka owes Virtusa LKR 175,000.00.", "full_answer": "Total outstanding payable to Virtusa for AIESEC Sri Lanka is LKR 175,000.00 across 2 documents."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාව Virtusa ට LKR 175,000.00 ක් ගෙවිය යුතුය.", "full_answer": "AIESEC ශ්‍රී ලංකාව Virtusa ට ගෙවිය යුතු සම්පූර්ණ මුදල LKR 175,000.00 ක් (ලේඛන 2) කි."},
    },
    {
        "question": "Virtusa ට ගෙවිය යුතු කීයද?",
        "plan": {"task": "aggregate_sum", "filters": [
            {"field": "flow_type", "op": "in", "value": ["payable", "cash_outflow"]},
            {"field": "vendor", "op": "contains", "value": "Virtusa"},
        ], "measure": {"field": "total", "agg": "sum"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 95000.00, "currency": "LKR", "row_count": 1, "operation": "aggregate_sum"},
        "answer_si": {"short_answer": "Virtusa ට ගෙවිය යුතු සම්පූර්ණ මුදල LKR 95,000.00 කි.", "full_answer": "AIESEC ශ්‍රී ලංකාව Virtusa ට ගෙවිය යුතු සම්පූර්ණ මුදල LKR 95,000.00 ක් (ලේඛනය 1) කි."},
        "answer_en": {"short_answer": "AIESEC Sri Lanka owes Virtusa LKR 95,000.00.", "full_answer": "Total outstanding payable to Virtusa for AIESEC Sri Lanka is LKR 95,000.00 (1 document)."},
    },
    # ── Count queries ──
    {
        "question": "How many invoices do we have this month?",
        "plan": {"task": "aggregate_count", "filters": [
            {"field": "doc_date", "op": "between", "value": [_this_month_start, today.isoformat()]},
        ], "measure": {"field": "item", "agg": "count"}, "group_by": [], "output": {"format": "number"}},
        "computed": {"value": 7, "currency": None, "row_count": 7, "operation": "aggregate_count"},
        "answer_en": {"short_answer": "AIESEC Sri Lanka has 7 invoices this month.", "full_answer": "There are 7 invoices for AIESEC Sri Lanka in the current month."},
        "answer_si": {"short_answer": "AIESEC ශ්‍රී ලංකාවේ මෙම මාසයේ ඉන්වොයිස් 7 ක් ඇත.", "full_answer": "AIESEC ශ්‍රී ලංකාව සඳහා මෙම මාසයේ ඉන්වොයිස් 7 ක් ඇත."},
    },
    # ── Average ──
    {
        "question": "What is the average invoice value from Classic Printers?",
        "plan": {"task": "aggregate_avg", "filters": [
            {"field": "vendor", "op": "contains", "value": "Classic Printers"},
        ], "measure": {"field": "total", "agg": "avg"}, "group_by": [], "output": {"format": "currency"}},
        "computed": {"value": 32500.00, "currency": "LKR", "row_count": 4, "operation": "aggregate_avg"},
        "answer_en": {"short_answer": "The average invoice value from Classic Printers for AIESEC Sri Lanka is LKR 32,500.00.", "full_answer": "Average invoice value from Classic Printers for AIESEC Sri Lanka is LKR 32,500.00, based on 4 documents."},
        "answer_si": {"short_answer": "Classic Printers වෙතින් AIESEC ශ්‍රී ලංකාවේ සාමාන්‍ය ඉන්වොයිස් අගය LKR 32,500.00 කි.", "full_answer": "Classic Printers වෙතින් AIESEC ශ්‍රී ලංකාව සඳහා ලේඛන 4 ක් ඇසුරෙන් ගණනය කළ සාමාන්‍ය ඉන්වොයිස් අගය LKR 32,500.00 කි."},
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_records_from_db() -> list[dict]:
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL not set — skipping DB records.")
        return []
    try:
        import psycopg
        import psycopg.rows
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT
                        "documentId", "documentType", "orderId", "flowType",
                        "companyName", "supplierName", "docDate", "currency",
                        "rawTotalAmount", "finalTotalAmount", "payableAmount",
                        "cashReturn", "taxAmount", "taxRate",
                        "receivedStatus", "paidStatus",
                        "rawText", "correctedText", "structuredJson"
                    FROM "FinancialDocument"
                    WHERE "deletedAt" IS NULL
                      AND "rawText" IS NOT NULL AND "rawText" != ''
                      AND "status" = 'confirmed'
                    ORDER BY "createdAt" DESC
                """)
                return cur.fetchall() or []
    except Exception as e:
        print(f"WARNING: Could not load DB records: {e}")
        return []


def _row_to_expected_json(row: dict) -> dict:
    def s(v): return str(v) if v is not None else ""
    return {
        "document_type": s(row.get("documentType")) or "unknown",
        "order_id": s(row.get("orderId")),
        "flow_type": s(row.get("flowType")) or "unknown",
        "company_name": s(row.get("companyName")),
        "supplier_name": s(row.get("supplierName")),
        "date": s(row.get("docDate")),
        "currency": s(row.get("currency")) or "LKR",
        "raw_total_amount": s(row.get("rawTotalAmount") or ""),
        "final_total_amount": s(row.get("finalTotalAmount") or ""),
        "payable_amount": s(row.get("payableAmount") or ""),
        "cash_return": s(row.get("cashReturn") or ""),
        "tax_amount": s(row.get("taxAmount") or ""),
        "tax_rate": s(row.get("taxRate") or ""),
        "received_status": s(row.get("receivedStatus")),
        "paid_status": s(row.get("paidStatus")),
        "items": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# BUILDER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def build_extraction_examples(db_rows: list[dict], n_extra_synthetic: int = 20) -> list[dict]:
    examples = []

    # From database
    for row in db_rows:
        raw = str(row.get("rawText") or "").strip()
        if not raw:
            continue
        expected = _row_to_expected_json(row)
        examples.append(_example(
            system=_EXTRACTION_SYSTEM,
            user=_EXTRACTION_USER_TEMPLATE.format(ocr_text=raw),
            model=json.dumps(expected, ensure_ascii=False, indent=2),
        ))

    # From synthetic templates
    for doc in _SYNTHETIC_DOCS:
        examples.append(_example(
            system=_EXTRACTION_SYSTEM,
            user=_EXTRACTION_USER_TEMPLATE.format(ocr_text=doc["ocr"]),
            model=json.dumps(doc["json"], ensure_ascii=False, indent=2),
        ))

    # Extra synthetic with light variation
    for _ in range(n_extra_synthetic):
        doc = random.choice(_SYNTHETIC_DOCS)
        varied_ocr = doc["ocr"].replace("2025", f"202{random.randint(4, 6)}")
        examples.append(_example(
            system=_EXTRACTION_SYSTEM,
            user=_EXTRACTION_USER_TEMPLATE.format(ocr_text=varied_ocr),
            model=json.dumps(doc["json"], ensure_ascii=False, indent=2),
        ))

    return examples


def build_correction_examples(db_rows: list[dict]) -> list[dict]:
    examples = []

    for row in db_rows:
        raw = str(row.get("rawText") or "").strip()
        corrected = str(row.get("correctedText") or "").strip()
        if not raw or not corrected or corrected == raw:
            continue
        examples.append(_example(
            system=_CORRECTION_SYSTEM,
            user=_CORRECTION_USER_TEMPLATE.format(raw_text=raw),
            model=corrected,
        ))

    # Synthetic correction examples
    for doc in _SYNTHETIC_DOCS:
        if doc["ocr"] != doc["corrected"]:
            examples.append(_example(
                system=_CORRECTION_SYSTEM,
                user=_CORRECTION_USER_TEMPLATE.format(raw_text=doc["ocr"]),
                model=doc["corrected"],
            ))

    return examples


def build_planning_examples(n_extra: int = 0) -> list[dict]:
    examples = []
    for pair in _QA_PAIRS:
        examples.append(_example(
            system=_PLANNING_SYSTEM,
            user=_PLANNING_USER_TEMPLATE.format(question=pair["question"], retry_note=""),
            model=json.dumps(pair["plan"], ensure_ascii=False),
        ))
    # Extra with light variation
    for _ in range(n_extra):
        pair = random.choice(_QA_PAIRS)
        examples.append(_example(
            system=_PLANNING_SYSTEM,
            user=_PLANNING_USER_TEMPLATE.format(
                question=pair["question"].replace("last month", "previous month"),
                retry_note="",
            ),
            model=json.dumps(pair["plan"], ensure_ascii=False),
        ))
    return examples


def build_answering_examples() -> list[dict]:
    examples = []
    for pair in _QA_PAIRS:
        computed_str = json.dumps(pair["computed"], ensure_ascii=False, indent=2)

        # English answer
        if "answer_en" in pair:
            examples.append(_example(
                system=_ANSWERING_SYSTEM.format(language="English"),
                user=_ANSWERING_USER_TEMPLATE.format(
                    language="English",
                    company_name="AIESEC Sri Lanka",
                    question=pair["question"],
                    computed_json=computed_str,
                ),
                model=json.dumps(pair["answer_en"], ensure_ascii=False),
            ))

        # Sinhala answer
        if "answer_si" in pair:
            examples.append(_example(
                system=_ANSWERING_SYSTEM.format(language="Sinhala"),
                user=_ANSWERING_USER_TEMPLATE.format(
                    language="Sinhala",
                    company_name="AIESEC ශ්‍රී ලංකාව",
                    question=pair["question"],
                    computed_json=computed_str,
                ),
                model=json.dumps(pair["answer_si"], ensure_ascii=False),
            ))

    return examples


# ─────────────────────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────────────────────

def _save_jsonl(examples: list[dict], path: Path, task: str):
    random.shuffle(examples)
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"  {task:12s}: {len(examples):4d} examples → {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Generate Gemini fine-tuning JSONL datasets")
    parser.add_argument("--synthetic", type=int, default=30,
                        help="Extra synthetic extraction examples (default 30)")
    parser.add_argument("--qa", type=int, default=20,
                        help="Extra synthetic Q&A planning examples (default 20)")
    args = parser.parse_args()

    print("Loading confirmed records from database...")
    db_rows = load_records_from_db()
    print(f"  Found {len(db_rows)} confirmed records.\n")

    print("Building fine-tuning datasets...")
    extraction = build_extraction_examples(db_rows, n_extra_synthetic=args.synthetic)
    correction = build_correction_examples(db_rows)
    planning   = build_planning_examples(n_extra=args.qa)
    answering  = build_answering_examples()

    print()
    _save_jsonl(extraction, OUTPUT_DIR / "gemini_extraction.jsonl",  "Extraction")
    _save_jsonl(correction, OUTPUT_DIR / "gemini_correction.jsonl",  "Correction")
    _save_jsonl(planning,   OUTPUT_DIR / "gemini_planning.jsonl",    "Planning")
    _save_jsonl(answering,  OUTPUT_DIR / "gemini_answering.jsonl",   "Answering")

    total = len(extraction) + len(correction) + len(planning) + len(answering)
    print(f"\nTotal: {total} fine-tuning examples across 4 task files.")
    print(f"Output directory: {OUTPUT_DIR}")
    print("\nNext step: upload to GCS and run scripts/vertex_ai_finetune.sh")


if __name__ == "__main__":
    main()
