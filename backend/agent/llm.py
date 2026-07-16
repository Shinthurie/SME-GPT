"""LangChain chat-model factory for the agentic query engine (Phase 1).

Reuses llm_client.py's provider selection (Gemini if GEMINI_API_KEY is set,
otherwise DeepSeek) so there is exactly one source of truth for which cloud
LLM is active -- this module only adapts that choice into a LangChain
BaseChatModel the LangGraph agent can bind tools to. pal_planner / pal_answer
/ ai_helper (the existing PAL + legacy query engines behind /ask-query) are
untouched and keep calling llm_client.call_llm directly.

There is no local (Ollama) fallback here either -- see the PRIVACY TRADE-OFF
note atop llm_client.py.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

import llm_client as _llm_client
from llm_client import LLMUnavailableError


def get_chat_model(temperature: float = 0.0) -> BaseChatModel:
    """Returns a tool-callable chat model for the active query provider.

    Raises LLMUnavailableError if neither GEMINI_API_KEY nor DEEPSEEK_API_KEY
    is configured.
    """
    if _llm_client.QUERY_PROVIDER == "gemini" and _llm_client.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise LLMUnavailableError(
                "GEMINI_API_KEY is set but langchain-google-genai is not installed. "
                "Install it (pip install langchain-google-genai), or unset "
                "GEMINI_API_KEY to fall back to DeepSeek for the agent engine."
            ) from exc

        return ChatGoogleGenerativeAI(
            model=_llm_client.GEMINI_TUNED_QUERY_MODEL or _llm_client.GEMINI_MODEL,
            google_api_key=_llm_client.GEMINI_API_KEY,
            temperature=temperature,
        )

    if _llm_client.DEEPSEEK_API_KEY:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=_llm_client.DEEPSEEK_BASE_URL,
            api_key=_llm_client.DEEPSEEK_API_KEY,
            model=_llm_client.DEEPSEEK_MODEL,
            temperature=temperature,
        )

    raise LLMUnavailableError(
        "No LLM provider is available for the agent query engine. Set "
        "GEMINI_API_KEY or DEEPSEEK_API_KEY (local Ollama inference has been removed)."
    )
