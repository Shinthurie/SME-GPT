"""
Expanded LLM Answer-Quality Evaluation Harness
==============================================
A larger, balanced, auto-graded successor to eval_answer_quality.py — built to
replace the small 16-question golden set with a statistically defensible sample.

Same principle: runs each question through the REAL live query engine
(pal_qa.answer_financial_question -> real DeepSeek calls), against a FIXED
synthetic dataset whose values are known exactly, so grading is objective and
needs no human judgement. Ground truth is COMPUTED from the dataset (never
hand-typed), so the expected answers can't drift out of sync.

Reports overall accuracy plus a breakdown by language (English vs Sinhala) and
by intent category — the numbers a dissertation panel actually asks for.

Run:  cd backend && python scripts/eval_answer_quality_expanded.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
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
_this_month = _today.replace(day=6)
_last_month = (_today.replace(day=1) - timedelta(days=1)).replace(day=6)


def _row(document_id, doc_date, supplier, flow_type, amount, document_type,
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


# ── Fixed synthetic dataset (16 documents) ──────────────────────────────────
_DOCS = [
    # Receivables (money owed TO us) — invoices, flow=receivable
    _row("IN101", _this_month, "Silva Traders",   "receivable",   15000.0, "invoice", received_status="not_received"),
    _row("IN102", _this_month, "Perera Stores",   "receivable",    8000.0, "invoice", received_status="not_received"),
    _row("IN103", _last_month, "Fernando & Sons", "receivable",   22000.0, "invoice", received_status="not_received"),
    _row("IN104", _last_month, "Gamage Retail",   "receivable",   11000.0, "invoice", received_status="not_received"),
    # Payables (money WE owe) — POs (always payable) + a payable invoice
    _row("PO201", _this_month, "Ceylon Traders",  "payable",      12000.0, "po",   paid_status="not_paid"),
    _row("PO202", _last_month, "Kandy Supplies",  "payable",       5000.0, "po",   paid_status="not_paid"),
    _row("IN105", _this_month, "Colombo Textiles","payable",       9000.0, "invoice", paid_status="not_paid"),
    # Cash inflow — receipts
    _row("R301",  _this_month, "Silva Traders",   "cash_inflow",  20000.0, "receipt"),
    _row("R302",  _last_month, "Perera Stores",   "cash_inflow",   7000.0, "receipt"),
    _row("R303",  _this_month, "Fernando & Sons", "cash_inflow",   9000.0, "receipt"),
    # Cash outflow — receipts
    _row("R304",  _this_month, "City Landlord",   "cash_outflow",  6000.0, "receipt"),
    _row("R305",  _this_month, "Power Board",     "cash_outflow",  4000.0, "receipt"),
    # Delivery notes (no amounts)
    _row("DN401", _this_month, "Ceylon Traders",  "expense",           0.0, "dn"),
    _row("DN402", _last_month, "Kandy Supplies",  "expense",           0.0, "dn"),
    _row("DN403", _this_month, "Colombo Textiles","expense",           0.0, "dn"),
    # One more invoice for count variety
    _row("IN106", _last_month, "Silva Traders",   "receivable",    6000.0, "invoice", received_status="not_received"),
]
_EVAL_ROWS = pd.DataFrame(_DOCS)


# ── Ground truth, COMPUTED from the dataset (not hand-typed) ─────────────────
def _sum(flow):
    return round(sum(d["final_total_amount"] for d in _DOCS if d["flow_type"] == flow), 2)

def _count(doc_type=None):
    return sum(1 for d in _DOCS if doc_type is None or d["document_type"] == doc_type)

def _supplier_payable(name):
    return round(sum(d["final_total_amount"] for d in _DOCS
                     if d["supplier_name"] == name and d["flow_type"] == "payable"), 2)

def _supplier_receivable(name):
    return round(sum(d["final_total_amount"] for d in _DOCS
                     if d["supplier_name"] == name and d["flow_type"] == "receivable"), 2)

GT = {
    "receivable": _sum("receivable"),          # 15000+8000+22000+11000+6000 = 62000
    "payable":    _sum("payable"),             # 12000+5000+9000 = 26000
    "cash_inflow":  _sum("cash_inflow"),       # 20000+7000+9000 = 36000
    "cash_outflow": _sum("cash_outflow"),      # 6000+4000 = 10000
    "count_total":   _count(),                 # 16
    "count_invoice": _count("invoice"),        # 5
    "count_receipt": _count("receipt"),        # 5
    "count_po":      _count("po"),             # 2
    "count_dn":      _count("dn"),             # 3
    "owe_ceylon":    _supplier_payable("Ceylon Traders"),   # 12000
    "owe_kandy":     _supplier_payable("Kandy Supplies"),   # 5000
    "recv_silva":    _supplier_receivable("Silva Traders"), # 15000+6000 = 21000
    "recv_fernando": _supplier_receivable("Fernando & Sons"), # 22000
}


def _fake_load_dataset(user_id: str = None):
    if user_id == EVAL_USER_ID:
        return _EVAL_ROWS.copy()
    return pd.DataFrame(columns=_EVAL_ROWS.columns)


def _num(text, expected):
    variants = [f"{expected:,.2f}", f"{expected:,.0f}", f"{expected:.2f}", f"{int(expected)}"]
    return any(v in (text or "") for v in variants)

def _any(text, kws):
    low = (text or "").lower()
    return any(k.lower() in low for k in kws)

def _none(text):
    return _any(text, ["0", "no ", "none", "not found", "could not find", "couldn't find", "no documents", "නැහැ", "නැත"])


# ── Question set: (question, language, category, grader) ─────────────────────
# grader(answer, success) -> bool.  ~40 questions, 20 EN / 20 SI, ground truth
# from GT above.
Q = [
    # ---- English ---------------------------------------------------------
    ("What is my total receivable amount?",        "en", "receivable",  lambda a, s: s and _num(a, GT["receivable"])),
    ("What is my total payable amount?",           "en", "payable",     lambda a, s: s and _num(a, GT["payable"])),
    ("What is my total cash inflow?",              "en", "cash_inflow", lambda a, s: s and _num(a, GT["cash_inflow"])),
    ("What is my total cash outflow?",             "en", "cash_outflow",lambda a, s: s and _num(a, GT["cash_outflow"])),
    ("How many documents do I have?",              "en", "count",       lambda a, s: s and str(GT["count_total"]) in (a or "")),
    ("How many invoices do I have?",               "en", "count",       lambda a, s: s and str(GT["count_invoice"]) in (a or "")),
    ("How many receipts do I have?",               "en", "count",       lambda a, s: s and str(GT["count_receipt"]) in (a or "")),
    ("How many purchase orders do I have?",        "en", "count",       lambda a, s: s and str(GT["count_po"]) in (a or "")),
    ("How many delivery notes do I have?",         "en", "count",       lambda a, s: s and str(GT["count_dn"]) in (a or "")),
    ("What do I owe Ceylon Traders?",              "en", "supplier",    lambda a, s: s and _num(a, GT["owe_ceylon"])),
    ("How much do I owe Kandy Supplies?",          "en", "supplier",    lambda a, s: s and _num(a, GT["owe_kandy"])),
    ("How much does Silva Traders owe me?",        "en", "supplier",    lambda a, s: s and _num(a, GT["recv_silva"])),
    ("What is the total for supplier ZebraNonexistentCorp?", "en", "empty", lambda a, s: _none(a)),
    ("Show me my receivable documents",            "en", "list",        lambda a, s: s and _any(a, ["Silva", "Perera", "Fernando", "Gamage", "IN101", "IN103"])),
    ("Show me my payable documents",               "en", "list",        lambda a, s: s and _any(a, ["Ceylon", "Kandy", "Colombo", "PO201", "IN105"])),
    ("List my invoices",                           "en", "list",        lambda a, s: s and _any(a, ["IN101", "IN102", "IN103", "Silva", "Perera"])),
    ("How much do I owe supplier Colombo Textiles?", "en", "supplier",  lambda a, s: s and _num(a, 9000)),
    ("Do I have any delivery notes?",              "en", "count",       lambda a, s: s and str(GT["count_dn"]) in (a or "")),
    ("What are my total payables?",                "en", "payable",     lambda a, s: s and _num(a, GT["payable"])),
    ("What is my total cash inflow amount?",       "en", "cash_inflow", lambda a, s: s and _num(a, GT["cash_inflow"])),
    # ---- Sinhala ---------------------------------------------------------
    ("මගේ මුළු ලැබිය යුතු මුදල කීයද?",              "si", "receivable",  lambda a, s: s and _num(a, GT["receivable"])),
    ("මගේ මුළු ගෙවිය යුතු මුදල කීයද?",             "si", "payable",     lambda a, s: s and _num(a, GT["payable"])),
    ("මගේ මුළු මුදල් ලැබීම් ප්‍රමාණය කීයද?",          "si", "cash_inflow", lambda a, s: s and _num(a, GT["cash_inflow"])),
    ("මගේ මුළු වියදම් ප්‍රමාණය කීයද?",                "si", "cash_outflow",lambda a, s: s and _num(a, GT["cash_outflow"])),
    ("මට කීයක් ලේඛන තියෙනවද?",                       "si", "count",       lambda a, s: s and str(GT["count_total"]) in (a or "")),
    ("මට ඉන්වොයිස් කීයක් තියෙනවද?",                 "si", "count",       lambda a, s: s and str(GT["count_invoice"]) in (a or "")),
    ("මට රිසිට් කීයක් තියෙනවද?",                     "si", "count",       lambda a, s: s and str(GT["count_receipt"]) in (a or "")),
    ("මට ඇණවුම් කීයක් තියෙනවද?",                     "si", "count",       lambda a, s: s and str(GT["count_po"]) in (a or "")),
    ("මට බෙදාහැරීම් කීයක් තියෙනවද?",                 "si", "count",       lambda a, s: s and str(GT["count_dn"]) in (a or "")),
    ("මට Ceylon Traders ට කීයක් ගෙවන්න තියෙනවද?",   "si", "supplier",    lambda a, s: s and _num(a, GT["owe_ceylon"])),
    ("මට Kandy Supplies ට කීයක් ගෙවන්න තියෙනවද?",   "si", "supplier",    lambda a, s: s and _num(a, GT["owe_kandy"])),
    ("Silva Traders මට කීයක් ගෙවන්න තියෙනවද?",       "si", "supplier",    lambda a, s: s and _num(a, GT["recv_silva"])),
    ("ZebraNonexistentCorp සඳහා මුළු මුදල කීයද?",   "si", "empty",       lambda a, s: _none(a)),
    ("මගේ ලැබිය යුතු ලේඛන පෙන්නන්න",                 "si", "list",        lambda a, s: s and _any(a, ["Silva", "Perera", "Fernando", "Gamage", "IN101"])),
    ("මගේ ගෙවිය යුතු ලේඛන පෙන්නන්න",                 "si", "list",        lambda a, s: s and _any(a, ["Ceylon", "Kandy", "Colombo", "PO201"])),
    ("මගේ ඉන්වොයිස් පෙන්නන්න",                       "si", "list",        lambda a, s: s and _any(a, ["IN101", "IN102", "Silva", "Perera"])),
    ("මගේ ලැබිය යුතු මුළු මුදල කීයද?",               "si", "receivable",  lambda a, s: s and _num(a, GT["receivable"])),
    ("මගේ ගෙවිය යුතු මුළු මුදල කීයද?",               "si", "payable",     lambda a, s: s and _num(a, GT["payable"])),
    ("මට Colombo Textiles ට කීයක් ගෙවන්න තියෙනවද?",  "si", "supplier",    lambda a, s: s and _num(a, 9000)),
    ("මට Fernando & Sons ගෙන් කීයක් ලැබිය යුතුද?",   "si", "supplier",    lambda a, s: s and _num(a, GT["recv_fernando"])),
]

# Some intents surface their result in the evidence/metrics of the response,
# not the sentence — grade list/lookup questions against the whole response.
_HAYSTACK_CATS = {"list"}


def run():
    import pal_qa

    print(f"Ground truth: {GT}\n")
    results = []
    with patch("data_tools.load_dataset", side_effect=_fake_load_dataset):
        for i, (question, lang, cat, grader) in enumerate(Q, 1):
            try:
                r = pal_qa.answer_financial_question(question, COMPANY, EVAL_USER_ID)
                answer = r.get("direct_answer", "") or ""
                success = bool(r.get("success"))
                # For list intents the matched documents live in the evidence,
                # not the summary sentence, so grade against the whole response.
                graded_text = answer if cat not in _HAYSTACK_CATS else \
                    answer + " " + json.dumps(r, ensure_ascii=False, default=str)
                passed = bool(grader(graded_text, success))
            except Exception as exc:
                answer, success, passed = f"[EXCEPTION] {exc}", False, False
            print(f"  [{i:2d}/{len(Q)}] {'PASS' if passed else 'FAIL'} {lang} {cat:12s} {question[:34]:34s} -> {answer[:55]}")
            results.append({"question": question, "lang": lang, "category": cat,
                            "answer": answer, "success": success, "passed": passed})

    def acc(subset):
        n = len(subset); p = sum(1 for r in subset if r["passed"])
        return p, n, round(100 * p / n, 1) if n else 0.0

    overall = acc(results)
    by_lang = {lg: acc([r for r in results if r["lang"] == lg]) for lg in ("en", "si")}
    cats = sorted({r["category"] for r in results})
    by_cat = {c: acc([r for r in results if r["category"] == c]) for c in cats}

    print("\n" + "=" * 60)
    print(f"OVERALL : {overall[0]}/{overall[1]}  ({overall[2]}%)")
    print(f"English : {by_lang['en'][0]}/{by_lang['en'][1]}  ({by_lang['en'][2]}%)")
    print(f"Sinhala : {by_lang['si'][0]}/{by_lang['si'][1]}  ({by_lang['si'][2]}%)")
    print("By category:")
    for c in cats:
        p, n, a = by_cat[c]
        print(f"   {c:14s} {p}/{n}  ({a}%)")

    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "dataset_docs": len(_DOCS), "ground_truth": GT,
        "overall": {"passed": overall[0], "total": overall[1], "accuracy_pct": overall[2]},
        "by_language": {lg: {"passed": v[0], "total": v[1], "accuracy_pct": v[2]} for lg, v in by_lang.items()},
        "by_category": {c: {"passed": v[0], "total": v[1], "accuracy_pct": v[2]} for c, v in by_cat.items()},
        "results": results,
    }
    path = REPORT_DIR / f"eval_expanded_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written: {path}")
    return report


if __name__ == "__main__":
    run()
