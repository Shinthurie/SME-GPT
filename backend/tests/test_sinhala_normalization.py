"""Regression tests for Sinhala finance-noun phrase coverage in
_SINHALA_VERB_MAP / normalize_query.

Locks in the fix for a gap where "මගේ මුළු ලැබීම් කීයද?" (what is my total
receivable?) had no English financial keyword left after normalization and
fell through route_question() to the generic "summary" intent instead of
"receivable" -- producing a weak fallback answer instead of a real one.
"""
from __future__ import annotations

import data_tools as dt


def _route(question: str) -> str:
    corrected, _ = dt.spell_correct_query(question)
    normalized = dt.normalize_query(corrected)
    return dt.route_question(normalized)


def test_total_receivable_routes_to_receivable_intent():
    assert _route("මගේ මුළු ලැබීම් කීයද?") == "receivable"


def test_total_income_routes_to_revenue_intent():
    assert _route("මගේ මුළු ආදායම කීයද?") == "revenue"


def test_total_expenses_routes_to_expenses_intent():
    assert _route("මගේ මුළු වියදම කීයද?") == "expenses"


def test_total_payable_routes_to_payable_intent():
    assert _route("මගේ මුළු ගෙවීම් කීයද?") == "payable"


def test_finance_nouns_never_fall_through_to_summary():
    questions = [
        "මගේ මුළු ලැබීම් කීයද?",
        "මගේ මුළු ආදායම කීයද?",
        "මගේ මුළු වියදම කීයද?",
        "මගේ මුළු ගෙවීම් කීයද?",
    ]
    for q in questions:
        assert _route(q) != "summary", f"{q!r} fell through to the generic summary intent"
