"""Component 3 — Answer generator: phrases the deterministic executor result
in Sinhala/English with citations (docs/components/component-3.md "Output").
The LLM only rephrases numbers the executor already computed; it never
invents one -- enforced the same way ai_helper.generate_explainable_answer
enforces it: a strict "use only this JSON" prompt, plus a deterministic
fallback template if DeepSeek is unavailable or returns something unusable.
"""
from __future__ import annotations

import json

from ai_helper import call_ollama
from llm_correction import count_sinhala_chars

_ANSWER_PROMPT = """You are a financial assistant. Answer in {language}.

Rules:
- Use ONLY the numbers in the Computed Result below -- never invent or adjust a number
- The short answer must be one business-friendly sentence
- The full answer may add brief context (currency, row count, document count)
- If currency is "mixed", say the totals are split by currency and list each amount
- Do not mention hidden reasoning or the word "plan"

Return ONLY valid JSON in this exact shape:
{{"short_answer": "", "full_answer": ""}}

Company: {company_name}
Question: {question}
Computed Result:
{computed_json}
""".strip()


def detect_language(question: str) -> str:
    """Sinhala if a meaningful fraction of the question is Sinhala script
    (U+0D80-U+0DFF), else English -- same detection approach used elsewhere
    in the pipeline (see docs/components/component-1.md)."""
    return "Sinhala" if count_sinhala_chars(question) >= max(3, len(question) // 4) else "English"


def _format_money(value, currency: str | None) -> str:
    if isinstance(value, (int, float)):
        return f"{currency or 'LKR'} {value:,.2f}"
    return str(value)


def build_fallback_answer(company_name: str, plan: dict, computed: dict) -> tuple[str, str]:
    value = computed.get("value")
    currency = computed.get("currency")
    row_count = computed.get("row_count", 0)
    operation = computed.get("operation", plan.get("task", ""))

    if computed.get("per_currency"):
        breakdown = ", ".join(f"{b['currency']} {b['value']:,.2f}" for b in computed["per_currency"])
        short = f"For {company_name}, totals are split by currency: {breakdown}."
        full = (
            f"{operation} over {row_count} matching row(s) for '{company_name}', split by "
            f"currency since they don't share one: {breakdown}."
        )
        return short, full

    formatted = _format_money(value, currency)
    short = f"For {company_name}, {operation} = {formatted}."
    full = f"Computed {operation} over {row_count} matching row(s) for '{company_name}'. Result: {formatted}."
    return short, full


def generate_pal_answer(question: str, company_name: str, plan: dict, computed: dict) -> dict:
    language = detect_language(question)
    prompt = _ANSWER_PROMPT.format(
        language=language, company_name=company_name, question=question,
        computed_json=json.dumps(computed, ensure_ascii=False, default=str, indent=2),
    )

    try:
        raw_reply = call_ollama(prompt)
        start, end = raw_reply.find("{"), raw_reply.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw_reply[start:end + 1])
            short_answer = str(parsed.get("short_answer", "")).strip()
            full_answer = str(parsed.get("full_answer", "")).strip()
            if short_answer and full_answer:
                return {"short_answer": short_answer, "full_answer": full_answer}
    except Exception:
        pass

    short_answer, full_answer = build_fallback_answer(company_name, plan, computed)
    return {"short_answer": short_answer, "full_answer": full_answer}
