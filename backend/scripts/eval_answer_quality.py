"""
LLM Answer-Quality Evaluation Harness
======================================
Runs a fixed golden-question set through the REAL live pipeline
(pal_qa.answer_financial_question -> real Gemini/DeepSeek/Ollama calls via
llm_client.call_llm, whichever provider is currently configured/active) and
grades each answer. Unlike the pytest suite (~419 tests, all hermetic --
every LLM call monkeypatched, e.g. tests/test_iter5_pal_qa.py), this
deliberately makes real network calls, so it is NOT run as part of
`pytest`/CI. Run manually:

    cd backend
    python scripts/eval_answer_quality.py

The underlying dataset (`load_dataset`) is monkeypatched for a fixed
EVAL_USER_ID so the harness is deterministic and doesn't depend on the
live Postgres/OCR pipeline (which has real-world flakiness -- e.g. the
Colab OCR tunnel disconnecting) -- only the answer-generation step is real.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

_backend = Path(__file__).resolve().parent.parent
load_dotenv(_backend / ".env")
sys.path.insert(0, str(_backend))

import pandas as pd  # noqa: E402

REPORT_DIR = _backend / "eval_reports"
REPORT_DIR.mkdir(exist_ok=True)

EVAL_USER_ID = "eval-harness-user"
COMPANY = "Eval Test Co"

_today = date.today()
_this_month = _today.replace(day=5)
_last_month = (_today.replace(day=1) - timedelta(days=1)).replace(day=5)


def _row(document_id, doc_date, supplier, flow_type, amount, document_type="invoice",
         received_status="NULL", paid_status="NULL", order_id="NULL"):
    return {
        "user_id": EVAL_USER_ID,
        "document_id": document_id, "date": doc_date.isoformat(), "supplier_name": supplier,
        "company_name": COMPANY, "flow_type": flow_type, "currency": "LKR",
        "items": [{"description": "Item", "quantity": 1, "unit_price": amount, "line_total": amount}],
        "final_total_amount": amount, "payable_amount": amount, "raw_total_amount": amount,
        "document_type": document_type, "order_id": order_id,
        "received_status": received_status, "paid_status": paid_status,
    }


# Known, hand-computed ground truth:
#   total_receivable_amount = 10000 (INV-1, unreceived)
#   total_payable_amount    = 2000 (PO-1) + 4000 (INV-2) = 6000 (both unpaid)
#   net_this_month  = +10000(INV-1) +5000(REC-1) -3000(R-1) -2000(PO-1) = +10000
#   net_last_month  = +12000(REC-2) -4000(INV-2) = +8000
#   document_count  = 6
_EVAL_ROWS = pd.DataFrame([
    _row("INV-1", _this_month, "Client A", "receivable", 10000.0, "invoice"),
    _row("REC-1", _this_month, "Client B", "cash_inflow", 5000.0, "receipt"),
    _row("R-1", _this_month, "Landlord", "cash_outflow", 3000.0, "receipt"),
    _row("PO-1", _this_month, "Vendor A", "payable", 2000.0, "po"),
    _row("INV-2", _last_month, "Vendor B", "payable", 4000.0, "invoice"),
    _row("REC-2", _last_month, "Client C", "cash_inflow", 12000.0, "receipt"),
])


def _fake_load_dataset(user_id: str = None):
    if user_id == EVAL_USER_ID:
        return _EVAL_ROWS.copy()
    return pd.DataFrame(columns=_EVAL_ROWS.columns)


def _contains_number(text: str, expected: float) -> bool:
    """Tolerant match: accepts 10000, 10,000, 10000.0, 10,000.00, etc."""
    variants = [
        f"{expected:,.2f}", f"{expected:,.0f}",
        f"{expected:.2f}", f"{int(expected)}",
    ]
    return any(v in text for v in variants)


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


# ── Golden question set (16) ────────────────────────────────────────────────
# Each case: (question, grader) where grader(answer_text, success) -> bool
QUESTIONS = [
    ("What is my total receivable amount?",
     lambda a, s: s and _contains_number(a, 10000)),
    ("What is my total payable amount?",
     lambda a, s: s and _contains_number(a, 6000)),
    ("How many documents do I have?",
     lambda a, s: s and "6" in a),
    ("How many invoices do I have?",
     lambda a, s: s and "2" in a),
    ("What do I owe Vendor A?",
     lambda a, s: s and _contains_number(a, 2000)),
    ("How can I manage my budget better?",
     lambda a, s: s and _contains_any(a, ["10,000", "10000", "receivable", "budget"])),
    ("How do I reduce my payables?",
     lambda a, s: s and _contains_any(a, ["6,000", "6000", "payable"])),
    ("What is the total for supplier NonexistentCorp?",
     lambda a, s: _contains_any(a, ["0", "no", "not found", "could not find", "couldn't find"])),
    ("What is my net cash flow this month?",
     lambda a, s: s and _contains_number(a, 10000)),
    ("Show me my receivable documents",
     lambda a, s: s and _contains_any(a, ["Client A", "INV-1"])),
    # Sinhala
    ("මගේ මුළු ලැබීම් කීයද?",
     lambda a, s: s and _contains_number(a, 10000)),
    ("මගේ මුළු ගෙවීම් කීයද?",
     lambda a, s: s and _contains_number(a, 6000)),
    ("මට කීයක් ලේඛන තියෙනවද?",
     lambda a, s: s and "6" in a),
    ("මගේ අයවැය කළමනාකරණය කරන්නේ කොහොමද?",
     lambda a, s: s and _contains_any(a, ["10,000", "10000", "budget", "අයවැය"])),
    ("මට Vendor A ට කීයක් ගෙවන්න තියෙනවද?",
     lambda a, s: s and _contains_number(a, 2000)),
    ("මගේ මුළු ආදායම කීයද?",
     lambda a, s: s and (_contains_number(a, 10000) or _contains_number(a, 5000))),
]


def run():
    import pal_qa

    results = []
    with patch("data_tools.load_dataset", side_effect=_fake_load_dataset):
        for i, (question, grader) in enumerate(QUESTIONS, 1):
            try:
                result = pal_qa.answer_financial_question(question, COMPANY, EVAL_USER_ID)
                answer = result.get("direct_answer", "") or ""
                success = bool(result.get("success"))
                passed = bool(grader(answer, success))
            except Exception as exc:
                answer, success, passed = f"[EXCEPTION] {exc}", False, False

            status = "PASS" if passed else "FAIL"
            print(f"  [{i:2d}/{len(QUESTIONS)}] {status}  {question[:50]:50s}  -> {answer[:70]}")
            results.append({
                "question": question, "answer": answer,
                "success": success, "passed": passed,
            })

    n_pass = sum(1 for r in results if r["passed"])
    accuracy = round(100 * n_pass / len(results), 1) if results else 0.0
    print(f"\nAccuracy: {n_pass}/{len(results)} ({accuracy}%)")

    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "accuracy_pct": accuracy,
        "passed": n_pass,
        "total": len(results),
        "results": results,
    }
    report_path = REPORT_DIR / f"eval_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report written: {report_path}")
    return report


if __name__ == "__main__":
    run()
