"""Regression tests for query spell-correction (data_tools.spell_correct_query).

Guards the bug where a quoted supplier name "Lanka Beverage Supplies" had
"Supplies" auto-corrected to "Suppliers", which re-routed a payable question
into a supplier-list dump.
"""
import data_tools as dt


def test_quoted_entity_name_is_not_corrected():
    q = 'how much do we owe "Lanka Beverage Supplies"?'
    corrected, corrections = dt.spell_correct_query(q)
    assert '"Lanka Beverage Supplies"' in corrected
    assert corrections == []


def test_quoted_owe_question_routes_to_payable_not_supplier_list():
    q = 'how much do we owe "Lanka Beverage Supplies"?'
    corrected, _ = dt.spell_correct_query(q)
    assert dt.route_question(dt.normalize_query(corrected)) == "payable"


def test_supplies_is_not_corrected_even_unquoted():
    corrected, corrections = dt.spell_correct_query("how much do we owe Lanka Beverage Supplies?")
    assert "Suppliers" not in corrected
    assert corrections == []


def test_genuine_typo_still_corrected():
    corrected, corrections = dt.spell_correct_query("show my payahles")
    assert "payables" in corrected
    assert corrections
