"""Financial advisory path for the /ask-query chatbot.

Handles advice-seeking questions ("how can I manage my budget", "how do I bring
down receivables") as a distinct question class from the factual PAL/legacy
engines: it grounds the LLM's reasoning in the user's real financial snapshot
(data_tools.get_financial_snapshot) plus general financial best-practice
knowledge, and keeps short conversational context so follow-ups make sense.
"""
from __future__ import annotations

import data_tools as dt
from llm_client import call_llm
from llm_correction import count_sinhala_chars

SOURCE = "Financial Advisor (LLM + live financial snapshot)"

# Distinctive substring of the fixed explanation text this module always returns
# (see generate_financial_advice below) -- used by pal_qa.py to recognize "we're
# already mid-advisory-conversation" so a plain reply to a clarifying question
# (e.g. "my expenses are rent 50000...") stays on this path even though the
# reply itself doesn't look like an advice-seeking question in isolation.
EXPLANATION_MARKER = "analysing your current financial snapshot"


def continues_advisory_conversation(conversation_history: list[dict] | None) -> bool:
    if not conversation_history:
        return False
    last_explanation = conversation_history[-1].get("explanation", "") or ""
    return EXPLANATION_MARKER in last_explanation


def _detect_lang(question: str) -> str:
    return "si" if count_sinhala_chars(question) >= max(3, len(question) // 4) else "en"


def _format_snapshot(snapshot: dict) -> str:
    lines = [
        f"Total outstanding receivable: {snapshot['total_receivable_amount']}",
        f"Total outstanding payable: {snapshot['total_payable_amount']}",
        f"Net cash flow this month: {snapshot['net_this_month']}",
        f"Net cash flow last month: {snapshot['net_last_month']}",
        f"Number of documents on record: {snapshot['document_count']}",
    ]
    if snapshot["open_receivables"]:
        top = ", ".join(f"{e['supplier_name']} ({e['amount']})" for e in snapshot["open_receivables"])
        lines.append(f"Largest unpaid receivables: {top}")
    if snapshot["open_payables"]:
        top = ", ".join(f"{e['supplier_name']} ({e['amount']})" for e in snapshot["open_payables"])
        lines.append(f"Largest unpaid payables: {top}")
    if snapshot["budgets"]:
        budget_str = ", ".join(f"{k}: {v}" for k, v in snapshot["budgets"].items())
        lines.append(f"Saved monthly budget targets: {budget_str}")
    else:
        lines.append("No monthly budget targets saved yet.")
    return "\n".join(lines)


def _format_history(conversation_history: list[dict] | None) -> str:
    if not conversation_history:
        return "(no prior turns in this conversation)"
    turns = []
    for turn in conversation_history[-6:]:
        q = turn.get("question", "")
        a = turn.get("answer", "")
        if q or a:
            turns.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(turns) if turns else "(no prior turns in this conversation)"


def generate_financial_advice(
    question: str,
    company_name: str,
    user_id: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    snapshot = dt.get_financial_snapshot(user_id, company_name)
    lang = _detect_lang(question)
    lang_instruction = "Reply in Sinhala." if lang == "si" else "Reply in English."

    system = (
        "You are the financial advisory hub for a Sri Lankan small/medium enterprise (SME) "
        "owner -- an ongoing planning partner, not a one-shot report generator. You are given "
        "the business's real, current financial snapshot below and the conversation so far.\n\n"
        "Ground your advice in the real numbers wherever relevant (cite specific figures), and "
        "combine that with general financial best-practice guidance where the data alone isn't "
        "enough. Be specific and actionable, not generic.\n\n"
        "PLANNING REQUESTS: if the user asks you to help plan a period (e.g. \"help me plan next "
        "month\", \"help me budget\") and you don't yet have the information needed to build a "
        "concrete plan (e.g. their expected income/expenses for that period, a specific goal), "
        "do NOT guess or pad the answer with generic filler -- ask ONE focused clarifying "
        "question instead (e.g. \"What expenses do you expect next month?\"). Once they answer in "
        "a later turn, use that answer together with the real snapshot below to build a concrete, "
        "numbered plan. Look at the conversation so far first: if they already answered a "
        "clarifying question you (or the conversation) asked earlier, use that information now "
        "instead of asking again.\n\n"
        "IMPROVEMENT REQUESTS (\"how do I reduce receivables\", \"how do I cut expenses\"): give "
        "concrete, prioritized, actionable steps grounded in the real snapshot -- name the actual "
        "suppliers/amounts involved where relevant, not just generic advice.\n\n"
        "Keep answers concise (short paragraphs or a short bulleted/numbered list). "
        f"{lang_instruction}"
    )

    prompt = (
        f"Business financial snapshot:\n{_format_snapshot(snapshot)}\n\n"
        f"Conversation so far:\n{_format_history(conversation_history)}\n\n"
        f"Current question: {question}"
    )

    try:
        answer_text = call_llm(prompt, system=system).strip()
    except Exception as exc:
        answer_text = (
            "I couldn't generate advice right now (the language model is unavailable). "
            f"Here is your current snapshot instead: {_format_snapshot(snapshot)}"
        )
        return {
            "success": False,
            "direct_answer": answer_text, "short_answer": answer_text, "full_answer": answer_text,
            "explanation": answer_text, "evidence": [], "metrics": snapshot,
            "source_file": SOURCE, "computed": None, "citations": [],
            "audit": {"engine": "financial_advisor", "error": str(exc)},
        }

    explanation = (
        "This advice was generated by analysing your current financial snapshot "
        "(outstanding receivables/payables, this month's net cash flow, and your saved "
        "budget targets) together with general financial best practices."
    )

    return {
        "success": True,
        "direct_answer": answer_text,
        "short_answer": answer_text,
        "full_answer": answer_text,
        "explanation": explanation,
        "evidence": [],
        "metrics": snapshot,
        "source_file": SOURCE,
        "computed": None,
        "citations": [],
        "audit": {"engine": "financial_advisor"},
    }
