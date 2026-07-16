"""Grounding guard for the agent's final answer.

Generalizes pal_answer.py's single-plan grounding check to a multi-tool-call
agent turn: the LLM may only restate a monetary/numeric figure that a tool
call in this turn actually returned. Anything else means the LLM computed or
invented a number, which the architecture forbids end-to-end (the LLM plans
by calling deterministic tools -- pal_executor/pal_validator do the math --
docs/components/component-3.md "Why"). This is the last line of defense,
mirrored from pal_answer._collect_allowed_numbers / _answer_is_grounded.
"""
from __future__ import annotations

import json
import re

_MONEY_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{4,}")


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _collect_numbers(value, out: set[float]) -> None:
    if _is_number(value):
        out.add(round(float(value), 2))
    elif isinstance(value, dict):
        for v in value.values():
            _collect_numbers(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_numbers(v, out)


def collect_allowed_numbers(tool_outputs: list) -> set[float]:
    """Every number present anywhere in this turn's tool results. tool_outputs
    are ToolMessage.content values -- usually dicts, sometimes JSON strings."""
    allowed: set[float] = set()
    for content in tool_outputs:
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (ValueError, TypeError):
                continue
        _collect_numbers(content, allowed)
    return allowed


def answer_is_grounded(text: str, allowed: set[float]) -> bool:
    """False if `text` states a monetary-looking number no tool call produced."""
    for token in _MONEY_TOKEN_RE.findall(text or ""):
        plain_int = "," not in token and "." not in token
        num = float(token.replace(",", ""))
        if plain_int and 1900 <= num <= 2100:
            continue  # a year, not a monetary figure
        if not any(abs(num - a) <= max(0.5, abs(a) * 0.001) for a in allowed):
            return False
    return True
