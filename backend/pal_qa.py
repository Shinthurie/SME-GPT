"""Component 3 — orchestrator: Scope Resolver -> Planner -> Validator ->
Executor -> Answer Generator (docs/components/component-3.md "Flow"), wired
into the live /ask-query endpoint (app.py).

Falls back to the pre-PAL ad-hoc logic (data_tools.analyze_financial_query +
ai_helper.generate_explainable_answer) whenever PAL can't confidently
answer: DeepSeek is unavailable, the plan never validates within the retry
budget, the question doesn't map to one of PAL's arithmetic tasks (e.g.
"list my invoices"), or the validated plan matched zero rows. This keeps
every existing live query working while adding hallucination-free
arithmetic with citations for the cases PAL covers -- the same
"deterministic fallback when the LLM can't be trusted" philosophy as
ocr_correction.safe_correct() and ai_helper.build_fallback_answer.
"""
from __future__ import annotations

import data_tools as dt
from ai_helper import generate_explainable_answer
from pal_answer import generate_pal_answer
from pal_executor import execute_plan
from pal_planner import plan_query
from pal_scope import build_row_records, resolve_scope
from pal_validator import validate_plan

MAX_RETRIES = 2
SOURCE = "FinancialDocument + LineItem (Postgres)"

# Listing-style intents aren't arithmetic questions -- skip straight to the
# legacy path rather than spending a planner call that can't help.
_NON_ARITHMETIC_INTENTS = {"invoice_list", "receipt_list", "po_list", "dn_list"}


def _legacy_answer(question: str, company_name: str, user_id: str, *, audit_extra: dict | None = None) -> dict:
    analysis_result = dt.analyze_financial_query(question=question, company_name=company_name, user_id=user_id)
    answer_bundle = generate_explainable_answer(question=question, company_name=company_name, result=analysis_result)
    return {
        "success": analysis_result.get("success", False),
        "direct_answer": analysis_result.get("direct_answer") or answer_bundle.get("short_answer", ""),
        "short_answer": answer_bundle.get("short_answer", ""),
        "full_answer": answer_bundle.get("full_answer", analysis_result.get("explanation", "")),
        "explanation": answer_bundle.get("full_answer", analysis_result.get("explanation", "")),
        "evidence": analysis_result.get("evidence", []),
        "metrics": analysis_result.get("metrics", {}),
        "source_file": analysis_result.get("source_file", ""),
        "computed": None,
        "citations": [],
        "audit": {"engine": "legacy_ad_hoc", **(audit_extra or {})},
    }


def _empty_scope_answer(message: str) -> dict:
    return {
        "success": False, "direct_answer": message, "short_answer": message, "full_answer": message,
        "explanation": message, "evidence": [], "metrics": {}, "source_file": SOURCE,
        "computed": None, "citations": [], "audit": {"engine": "pal", "validation": "scope_empty"},
    }


def answer_financial_question(question: str, company_name: str, user_id: str) -> dict:
    question_type = dt.route_question(question)
    if question_type in _NON_ARITHMETIC_INTENTS:
        return _legacy_answer(question, company_name, user_id)

    documents_df, scope_error = resolve_scope(company_name, user_id)
    if scope_error:
        return _empty_scope_answer(scope_error)

    rows = build_row_records(documents_df)

    plan = None
    error_reason = None
    attempts = []
    for attempt in range(MAX_RETRIES + 1):
        candidate_plan = plan_query(question, error_reason=error_reason)
        if candidate_plan is None:
            attempts.append({"attempt": attempt, "plan": None, "error": "planner_unavailable_or_unparseable"})
            break
        is_valid, error_reason = validate_plan(candidate_plan)
        attempts.append({"attempt": attempt, "plan": candidate_plan, "error": None if is_valid else error_reason})
        if is_valid:
            plan = candidate_plan
            break

    if plan is None:
        # PAL couldn't produce a valid plan within the retry budget -> degrade
        # to the legacy path rather than failing the user's query outright
        # (component-3.md failure table: degrade to best available).
        return _legacy_answer(question, company_name, user_id, audit_extra={"pal_attempts": attempts})

    computed = execute_plan(plan, rows)

    if not computed.get("row_count"):
        # Validated plan, but nothing matched (component-3.md failure table:
        # "No rows retrieved -> broaden retrieval"). Simplified for this
        # iteration: degrade to the legacy path instead of re-querying with
        # widened filters -- still grounded in the same real data.
        return _legacy_answer(
            question, company_name, user_id,
            audit_extra={"pal_attempts": attempts, "pal_plan": plan, "reason": "no_rows_matched"},
        )

    answer_bundle = generate_pal_answer(question, company_name, plan, computed)

    used_doc_ids = {r["document_id"] for r in computed.get("rows_used", [])}
    evidence_df = documents_df[documents_df["document_id"].isin(used_doc_ids)]
    reason = f"PAL plan: {plan.get('task')} over canonical fields, validated against the allow-list."
    evidence = dt.build_evidence(evidence_df, reason)

    return {
        "success": True,
        "direct_answer": answer_bundle["short_answer"],
        "short_answer": answer_bundle["short_answer"],
        "full_answer": answer_bundle["full_answer"],
        "explanation": answer_bundle["full_answer"],
        "evidence": evidence,
        "metrics": {
            "company_name": company_name,
            "task": plan.get("task"),
            "computed_value": computed.get("value"),
            "currency": computed.get("currency"),
            "row_count": computed.get("row_count"),
        },
        "source_file": SOURCE,
        "computed": computed,
        "citations": [],  # bbox citations land once C1/C2 are wired into the live pipeline
        "audit": {"engine": "pal", "plan": plan, "validation": "passed", "attempts": len(attempts)},
    }
