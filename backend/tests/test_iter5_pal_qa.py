"""Iteration 5 — Component 3 (Neuro-Symbolic PAL Arithmetic QA) tests.

Covers: the plan validator (allow-list), the deterministic pandas executor
(filters/aggregations/group-by/compare, no exec/eval), the scope resolver's
row-record flattening, the planner/answer-generator's DeepSeek boundaries
(monkeypatched, same hermetic pattern as the C1 tests), and the
answer_financial_question() orchestrator -- including its fallback to the
pre-PAL ad-hoc logic when DeepSeek can't produce a valid plan or the plan
matches no rows.
"""
import pandas as pd
import pytest

import pal_answer
import pal_planner
import pal_qa
from pal_executor import execute_plan
from pal_scope import build_row_records
from pal_validator import validate_plan


# ---------------------------------------------------------------------------
# pal_validator
# ---------------------------------------------------------------------------

def test_validate_plan_accepts_aggregate_sum():
    plan = {"task": "aggregate_sum", "filters": [{"field": "flow_type", "op": "eq", "value": "payable"}],
            "measure": {"field": "total", "agg": "sum"}, "group_by": []}
    assert validate_plan(plan) == (True, "")


def test_validate_plan_rejects_unknown_task():
    is_valid, reason = validate_plan({"task": "delete_everything", "measure": {"field": "total", "agg": "sum"}})
    assert is_valid is False
    assert "task_not_in_allowlist" in reason


def test_validate_plan_rejects_unsupported_filter_op():
    plan = {"task": "aggregate_sum", "filters": [{"field": "total", "op": "regex", "value": ".*"}],
            "measure": {"field": "total", "agg": "sum"}}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "operator_not_in_allowlist" in reason


def test_validate_plan_rejects_non_canonical_field_in_filters():
    plan = {"task": "aggregate_sum", "filters": [{"field": "secret_internal_id", "op": "eq", "value": "x"}],
            "measure": {"field": "total", "agg": "sum"}}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "field_not_canonical" in reason


def test_validate_plan_rejects_ambiguous_missing_measure_field():
    plan = {"task": "aggregate_sum", "filters": [], "measure": {"agg": "sum"}}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "ambiguous_target_field" in reason


def test_validate_plan_rejects_non_canonical_measure_field():
    plan = {"task": "aggregate_sum", "measure": {"field": "made_up_field", "agg": "sum"}}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "field_not_canonical" in reason


def test_validate_plan_rejects_unsupported_aggregation():
    plan = {"task": "aggregate_sum", "measure": {"field": "total", "agg": "median"}}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "aggregation_not_in_allowlist" in reason


def test_validate_plan_group_by_sum_requires_group_by():
    plan = {"task": "group_by_sum", "measure": {"field": "total", "agg": "sum"}, "group_by": []}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "group_by_sum_requires_a_non_empty_group_by" in reason


def test_validate_plan_lookup_value_requires_filters():
    plan = {"task": "lookup_value", "measure": {"field": "unit_price"}, "filters": []}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "lookup_value_requires_at_least_one_filter" in reason


def test_validate_plan_compare_requires_two_filter_sets():
    plan = {"task": "compare", "measure": {"field": "total", "agg": "sum"}, "compare_filters": [[]]}
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "compare_requires_exactly_two_filter_sets" in reason


def test_validate_plan_compare_validates_each_filter_set():
    plan = {
        "task": "compare", "measure": {"field": "total", "agg": "sum"},
        "compare_filters": [[{"field": "total", "op": "eq", "value": 1}], [{"field": "bogus", "op": "eq", "value": 1}]],
    }
    is_valid, reason = validate_plan(plan)
    assert is_valid is False
    assert "field_not_canonical" in reason


def test_validate_plan_not_a_dict():
    assert validate_plan(None) == (False, "plan_is_not_an_object")


# ---------------------------------------------------------------------------
# pal_executor
# ---------------------------------------------------------------------------

_ROWS = [
    {"document_id": "INV1", "line_no": 1, "vendor": "Acme", "flow_type": "payable", "currency": "LKR",
     "doc_date": "2025-01-10", "item": "Apple", "description": "Apple", "qty": 5, "unit_price": 100.0, "total": 500.0},
    {"document_id": "INV1", "line_no": 2, "vendor": "Acme", "flow_type": "payable", "currency": "LKR",
     "doc_date": "2025-01-10", "item": "Banana", "description": "Banana", "qty": 2, "unit_price": 50.0, "total": 100.0},
    {"document_id": "INV2", "line_no": 1, "vendor": "Beta Co", "flow_type": "receivable", "currency": "LKR",
     "doc_date": "2025-02-05", "item": "Cherry", "description": "Cherry", "qty": 1, "unit_price": 300.0, "total": 300.0},
]


def test_execute_aggregate_sum_with_filter():
    plan = {"task": "aggregate_sum", "filters": [{"field": "flow_type", "op": "eq", "value": "payable"}],
            "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, _ROWS)
    assert result["value"] == 600.0
    assert result["currency"] == "LKR"
    assert result["row_count"] == 2


def test_execute_aggregate_count():
    plan = {"task": "aggregate_count", "filters": [], "measure": {"field": "item", "agg": "count"}}
    result = execute_plan(plan, _ROWS)
    assert result["value"] == 3


def test_execute_aggregate_avg():
    avg_plan = {"task": "aggregate_avg", "filters": [], "measure": {"field": "total", "agg": "avg"}}
    assert execute_plan(avg_plan, _ROWS)["value"] == pytest.approx((500 + 100 + 300) / 3)


def test_execute_measure_agg_is_authoritative_over_task_label():
    # `measure.agg` drives the actual operation -- TASKS has no
    # aggregate_max/aggregate_min, so "give me the max total" is expressed as
    # task=aggregate_sum (a category label) + measure.agg=max.
    max_plan = {"task": "aggregate_sum", "filters": [], "measure": {"field": "total", "agg": "max"}}
    assert execute_plan(max_plan, _ROWS)["value"] == 500.0


def test_execute_filter_contains():
    plan = {"task": "aggregate_sum", "filters": [{"field": "description", "op": "contains", "value": "ana"}],
            "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, _ROWS)
    assert result["value"] == 100.0  # only "Banana"


def test_execute_filter_between():
    plan = {"task": "aggregate_sum", "filters": [{"field": "total", "op": "between", "value": [150, 1000]}],
            "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, _ROWS)
    assert result["value"] == 800.0  # 500 + 300


def test_execute_filter_in():
    plan = {"task": "aggregate_count", "filters": [{"field": "vendor", "op": "in", "value": ["Acme", "Beta Co"]}],
            "measure": {"field": "document_id", "agg": "count"}}
    result = execute_plan(plan, _ROWS)
    assert result["row_count"] == 3


def test_execute_group_by_sum():
    plan = {"task": "group_by_sum", "filters": [], "measure": {"field": "total", "agg": "sum"}, "group_by": ["vendor"]}
    result = execute_plan(plan, _ROWS)
    groups = {g["vendor"]: g["total"] for g in result["groups"]}
    assert groups == {"Acme": 600.0, "Beta Co": 300.0}


def test_execute_lookup_value():
    plan = {"task": "lookup_value", "filters": [{"field": "item", "op": "eq", "value": "Cherry"}],
            "measure": {"field": "unit_price"}}
    result = execute_plan(plan, _ROWS)
    assert result["value"] == [300.0]
    assert result["row_count"] == 1


def test_execute_compare_computes_difference():
    plan = {
        "task": "compare", "measure": {"field": "total", "agg": "sum"},
        "compare_filters": [
            [{"field": "flow_type", "op": "eq", "value": "payable"}],
            [{"field": "flow_type", "op": "eq", "value": "receivable"}],
        ],
    }
    result = execute_plan(plan, _ROWS)
    assert result["value"][0]["value"] == 600.0
    assert result["value"][1]["value"] == 300.0
    assert result["difference"] == 300.0


def test_execute_mixed_currency_triggers_per_currency_breakdown():
    rows = _ROWS + [{"document_id": "INV3", "line_no": 1, "vendor": "Gamma", "flow_type": "payable",
                      "currency": "USD", "doc_date": "2025-03-01", "item": "X", "description": "X",
                      "qty": 1, "unit_price": 10.0, "total": 10.0}]
    plan = {"task": "aggregate_sum", "filters": [{"field": "flow_type", "op": "eq", "value": "payable"}],
            "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, rows)
    assert result["currency"] == "mixed"
    breakdown = {b["currency"]: b["value"] for b in result["per_currency"]}
    assert breakdown == {"LKR": 600.0, "USD": 10.0}


def test_execute_empty_rows_returns_no_value():
    plan = {"task": "aggregate_sum", "filters": [], "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, [])
    assert result["value"] is None
    assert result["row_count"] == 0


def test_execute_filter_on_missing_field_returns_no_rows():
    plan = {"task": "aggregate_sum", "filters": [{"field": "tax", "op": "gte", "value": 1}],
            "measure": {"field": "total", "agg": "sum"}}
    result = execute_plan(plan, _ROWS)
    assert result["row_count"] == 0


# ---------------------------------------------------------------------------
# pal_scope.build_row_records
# ---------------------------------------------------------------------------

def test_build_row_records_one_row_per_item():
    df = pd.DataFrame([{
        "document_id": "INV1", "date": "2025-01-10", "supplier_name": "Acme", "flow_type": "payable",
        "currency": "LKR", "items": [{"description": "Apple", "quantity": 5, "unit_price": 100.0, "line_total": 500.0}],
    }])
    rows = build_row_records(df)
    assert len(rows) == 1
    assert rows[0]["item"] == "Apple"
    assert rows[0]["total"] == 500.0
    assert rows[0]["vendor"] == "Acme"
    assert rows[0]["flow_type"] == "payable"


def test_build_row_records_synthesizes_total_when_line_total_missing():
    df = pd.DataFrame([{
        "document_id": "INV1", "date": "2025-01-10", "supplier_name": "Acme", "flow_type": "payable",
        "currency": "LKR", "items": [{"description": "Apple", "quantity": 5, "unit_price": 100.0, "line_total": None}],
    }])
    rows = build_row_records(df)
    assert rows[0]["total"] == 500.0


def test_build_row_records_no_items_falls_back_to_document_total():
    df = pd.DataFrame([{
        "document_id": "INV2", "date": "2025-02-05", "supplier_name": "Beta Co", "flow_type": "receivable",
        "currency": "LKR", "items": [], "final_total_amount": 750.0, "payable_amount": 0.0, "raw_total_amount": 0.0,
    }])
    rows = build_row_records(df)
    assert len(rows) == 1
    assert rows[0]["total"] == 750.0
    assert rows[0]["line_no"] is None


def test_build_row_records_defaults_missing_currency_to_lkr():
    df = pd.DataFrame([{
        "document_id": "INV3", "date": "NULL", "supplier_name": "NULL", "flow_type": "unknown",
        "currency": "NULL", "items": [], "final_total_amount": 0.0, "payable_amount": 0.0, "raw_total_amount": 0.0,
    }])
    rows = build_row_records(df)
    assert rows[0]["currency"] == "LKR"


# ---------------------------------------------------------------------------
# pal_planner / pal_answer (DeepSeek boundary monkeypatched, hermetic)
# ---------------------------------------------------------------------------

def test_plan_query_parses_valid_json_reply(monkeypatch):
    monkeypatch.setattr(pal_planner, "call_ollama", lambda _p: '{"task": "aggregate_sum", "measure": {"field": "total", "agg": "sum"}}')
    plan = pal_planner.plan_query("How much do I owe?")
    assert plan["task"] == "aggregate_sum"


def test_plan_query_returns_none_on_unparseable_reply(monkeypatch):
    monkeypatch.setattr(pal_planner, "call_ollama", lambda _p: "not json at all")
    assert pal_planner.plan_query("anything") is None


def test_plan_query_returns_none_when_deepseek_unavailable(monkeypatch):
    monkeypatch.setattr(pal_planner, "call_ollama", lambda _p: (_ for _ in ()).throw(RuntimeError("offline")))
    assert pal_planner.plan_query("anything") is None


def test_plan_query_includes_retry_note_with_error_reason(monkeypatch):
    captured = {}
    monkeypatch.setattr(pal_planner, "call_ollama", lambda p: captured.setdefault("prompt", p) and '{"task": "aggregate_sum"}')
    pal_planner.plan_query("q", error_reason="field_not_canonical: 'bogus'")
    assert "field_not_canonical" in captured["prompt"]


def test_generate_pal_answer_uses_deepseek_reply_when_valid(monkeypatch):
    monkeypatch.setattr(pal_answer, "call_ollama", lambda _p: '{"short_answer": "S", "full_answer": "F"}')
    result = pal_answer.generate_pal_answer("q", "Acme", {"task": "aggregate_sum"}, {"value": 100, "currency": "LKR", "row_count": 1, "operation": "sum(total)"})
    assert result == {"short_answer": "S", "full_answer": "F"}


def test_generate_pal_answer_falls_back_when_deepseek_unavailable(monkeypatch):
    monkeypatch.setattr(pal_answer, "call_ollama", lambda _p: (_ for _ in ()).throw(RuntimeError("offline")))
    computed = {"value": 600.0, "currency": "LKR", "row_count": 2, "operation": "sum(total)"}
    result = pal_answer.generate_pal_answer("q", "Acme", {"task": "aggregate_sum"}, computed)
    assert "LKR 600.00" in result["short_answer"]


def test_generate_pal_answer_fallback_mentions_per_currency_breakdown(monkeypatch):
    monkeypatch.setattr(pal_answer, "call_ollama", lambda _p: (_ for _ in ()).throw(RuntimeError("offline")))
    computed = {"value": None, "currency": "mixed", "row_count": 2, "operation": "sum(total)",
                "per_currency": [{"currency": "LKR", "value": 600.0}, {"currency": "USD", "value": 10.0}]}
    result = pal_answer.generate_pal_answer("q", "Acme", {"task": "aggregate_sum"}, computed)
    assert "LKR 600.00" in result["short_answer"]
    assert "USD 10.00" in result["short_answer"]


def test_detect_language_sinhala_question():
    assert pal_answer.detect_language("මට කොච්චර ගෙවන්න තියෙනවද") == "Sinhala"


def test_detect_language_english_question():
    assert pal_answer.detect_language("How much do I owe Acme?") == "English"


# ---------------------------------------------------------------------------
# pal_qa.answer_financial_question (orchestrator)
# ---------------------------------------------------------------------------

_SCOPE_DF = pd.DataFrame([
    {"document_id": "INV1", "date": "2025-01-10", "supplier_name": "Acme", "company_name": "MyCo",
     "flow_type": "payable", "currency": "LKR", "items": [{"description": "Apple", "quantity": 5, "unit_price": 100.0, "line_total": 500.0}],
     "final_total_amount": 500.0, "payable_amount": 500.0, "raw_total_amount": 500.0,
     "document_type": "invoice", "order_id": "NULL", "received_status": "NULL", "paid_status": "NULL"},
])


def test_answer_financial_question_non_arithmetic_intent_uses_legacy_path(monkeypatch):
    monkeypatch.setattr(pal_qa.dt, "route_question", lambda _q: "invoice_list")
    monkeypatch.setattr(pal_qa.dt, "analyze_financial_query", lambda **_kw: {"success": True, "direct_answer": "legacy", "explanation": "legacy", "evidence": [], "metrics": {}, "source_file": "x"})
    monkeypatch.setattr(pal_qa, "generate_explainable_answer", lambda **_kw: {"short_answer": "legacy", "full_answer": "legacy"})

    result = pal_qa.answer_financial_question("show my invoices", "MyCo", "user1")
    assert result["audit"]["engine"] == "legacy_ad_hoc"
    assert result["direct_answer"] == "legacy"


def test_answer_financial_question_empty_scope_returns_not_found_message(monkeypatch):
    monkeypatch.setattr(pal_qa, "resolve_scope", lambda _company, _user: (pd.DataFrame(), "No records found for company 'MyCo' under the current user."))
    result = pal_qa.answer_financial_question("how much do I owe?", "MyCo", "user1")
    assert result["success"] is False
    assert "No records found" in result["direct_answer"]
    assert result["audit"]["validation"] == "scope_empty"


def test_answer_financial_question_pal_success_path(monkeypatch):
    monkeypatch.setattr(pal_qa.dt, "route_question", lambda _q: "payable")
    monkeypatch.setattr(pal_qa, "resolve_scope", lambda _company, _user: (_SCOPE_DF, None))
    plan = {"task": "aggregate_sum", "filters": [{"field": "flow_type", "op": "eq", "value": "payable"}],
            "measure": {"field": "total", "agg": "sum"}, "group_by": []}
    monkeypatch.setattr(pal_qa, "plan_query", lambda _q, error_reason=None: plan)
    monkeypatch.setattr(pal_qa, "generate_pal_answer", lambda *a, **kw: {"short_answer": "S", "full_answer": "F"})

    result = pal_qa.answer_financial_question("how much do I owe Acme?", "MyCo", "user1")

    assert result["success"] is True
    assert result["audit"]["engine"] == "pal"
    assert result["computed"]["value"] == 500.0
    assert result["metrics"]["task"] == "aggregate_sum"
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["document_id"] == "INV1"


def test_answer_financial_question_degrades_to_legacy_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(pal_qa.dt, "route_question", lambda _q: "payable")
    monkeypatch.setattr(pal_qa, "resolve_scope", lambda _company, _user: (_SCOPE_DF, None))
    monkeypatch.setattr(pal_qa, "plan_query", lambda _q, error_reason=None: {"task": "not_a_real_task"})
    monkeypatch.setattr(pal_qa.dt, "analyze_financial_query", lambda **_kw: {"success": True, "direct_answer": "legacy", "explanation": "legacy", "evidence": [], "metrics": {}, "source_file": "x"})
    monkeypatch.setattr(pal_qa, "generate_explainable_answer", lambda **_kw: {"short_answer": "legacy", "full_answer": "legacy"})

    result = pal_qa.answer_financial_question("how much do I owe?", "MyCo", "user1")

    assert result["audit"]["engine"] == "legacy_ad_hoc"
    assert len(result["audit"]["pal_attempts"]) == pal_qa.MAX_RETRIES + 1
    assert all(a["error"] for a in result["audit"]["pal_attempts"])


def test_answer_financial_question_degrades_to_legacy_when_plan_matches_no_rows(monkeypatch):
    monkeypatch.setattr(pal_qa.dt, "route_question", lambda _q: "payable")
    monkeypatch.setattr(pal_qa, "resolve_scope", lambda _company, _user: (_SCOPE_DF, None))
    plan = {"task": "aggregate_sum", "filters": [{"field": "vendor", "op": "eq", "value": "Nobody"}],
            "measure": {"field": "total", "agg": "sum"}, "group_by": []}
    monkeypatch.setattr(pal_qa, "plan_query", lambda _q, error_reason=None: plan)
    monkeypatch.setattr(pal_qa.dt, "analyze_financial_query", lambda **_kw: {"success": True, "direct_answer": "legacy", "explanation": "legacy", "evidence": [], "metrics": {}, "source_file": "x"})
    monkeypatch.setattr(pal_qa, "generate_explainable_answer", lambda **_kw: {"short_answer": "legacy", "full_answer": "legacy"})

    result = pal_qa.answer_financial_question("how much do I owe Nobody?", "MyCo", "user1")

    assert result["audit"]["engine"] == "legacy_ad_hoc"
    assert result["audit"]["reason"] == "no_rows_matched"
