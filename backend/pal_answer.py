"""Component 3 — Answer generator: phrases the deterministic executor result
in Sinhala/English with citations (docs/components/component-3.md "Output").
The LLM only rephrases numbers the executor already computed; it never
invents one -- enforced the same way ai_helper.generate_explainable_answer
enforces it: a strict "use only this JSON" prompt, plus a deterministic
fallback template if the query LLM is unavailable or returns something unusable.
"""
from __future__ import annotations

import json
import re

from llm_client import call_llm
from llm_correction import count_sinhala_chars

# Matches monetary-looking numbers: comma-grouped (1,000 / 105,000.00),
# decimals (50000.0), or bare integers of 4+ digits (100000). Single/short
# integers ("2 documents", "4 rows") are treated as counts, not money.
_MONEY_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{4,}")

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


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _collect_allowed_numbers(computed: dict) -> set[float]:
    """Every numeric value the executor actually produced. The answer LLM may
    only quote these -- any other monetary figure means it invented or
    (mis)computed one, which PAL forbids (the LLM never does arithmetic)."""
    allowed: set[float] = set()

    def add(v) -> None:
        if _is_number(v):
            allowed.add(round(float(v), 2))

    value = computed.get("value")
    add(value)
    if isinstance(value, list):
        for el in value:
            add(el.get("value")) if isinstance(el, dict) else add(el)
    add(computed.get("difference"))
    add(computed.get("row_count"))
    for b in computed.get("per_currency") or []:
        if isinstance(b, dict):
            add(b.get("value"))
    for g in computed.get("groups") or []:
        if isinstance(g, dict):
            for v in g.values():
                add(v)
    return allowed


def _answer_is_grounded(text: str, allowed: set[float]) -> bool:
    """False if the text states a monetary number the executor never computed."""
    for token in _MONEY_TOKEN_RE.findall(text or ""):
        plain_int = "," not in token and "." not in token
        num = float(token.replace(",", ""))
        if plain_int and 1900 <= num <= 2100:
            continue  # a year, not a monetary figure
        if not any(abs(num - a) <= max(0.5, abs(a) * 0.001) for a in allowed):
            return False
    return True


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
        raw_reply = call_llm(prompt, system="You are a financial assistant. Return ONLY valid JSON.", format="json")
        start, end = raw_reply.find("{"), raw_reply.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw_reply[start:end + 1])
            short_answer = str(parsed.get("short_answer", "")).strip()
            full_answer = str(parsed.get("full_answer", "")).strip()
            # Grounding guard: the LLM may only restate numbers the executor
            # computed. If it quotes a figure that isn't in the result (an
            # invented or miscomputed total), distrust the whole answer and use
            # the deterministic template instead. This is what actually enforces
            # "the LLM never computes numbers" at the answer stage.
            allowed = _collect_allowed_numbers(computed)
            if (short_answer and full_answer
                    and _answer_is_grounded(short_answer, allowed)
                    and _answer_is_grounded(full_answer, allowed)):
                return {"short_answer": short_answer, "full_answer": full_answer}
    except Exception:
        pass

    short_answer, full_answer = build_fallback_answer(company_name, plan, computed)
    return {"short_answer": short_answer, "full_answer": full_answer}


def build_discrepancy_bilingual_note(discrepancies: list[dict], lang: str = "en") -> str:
    """
    GAP-19C (Iter 19): generate a bilingual note about price discrepancies.
    Included in the answer when evidence contains an invoice+PO pair with a price gap.
    """
    actuals = [d for d in discrepancies if d.get("is_discrepancy")]
    if not actuals:
        return ""

    lines_en = []
    lines_si = []
    for d in actuals:
        sign = "+" if d.get("diff_pct", 0) > 0 else ""
        lines_en.append(
            f"• {d['description']}: invoice LKR {d['invoice_price']:,.2f} vs PO LKR {d['po_price']:,.2f} "
            f"({sign}{d['diff_pct']}% {d.get('direction', '')})"
        )
        lines_si.append(
            f"• {d['description']}: ඉන්වොයිස් LKR {d['invoice_price']:,.2f}, PO LKR {d['po_price']:,.2f} "
            f"({sign}{d['diff_pct']}% {d.get('direction', '')})"
        )

    en_block = "Price discrepancies detected:\n" + "\n".join(lines_en)
    si_block = "මිල විෂමතා හඳුනා ගන්නා ලදී:\n" + "\n".join(lines_si)

    if lang == "si":
        return f"{si_block}\n\n{en_block}"
    return f"{en_block}\n\n{si_block}"
