"""Agentic conversational query engine -- Phase 1 entry point.

Generalizes the PAL neuro-symbolic architecture (docs/components/component-3.md)
from a single rigid plan-execute-answer cycle into a multi-turn, tool-calling
conversation: the LLM still only *plans* by calling deterministic tools
(agent/tools.py); it never computes a number itself (agent/guard.py is the
last-line-of-defense check). Conversation memory persists per `thread_id`
(agent/memory.py). Tenant isolation is preserved exactly like the legacy/PAL
engines: user_id is bound into the tools server-side, never an LLM-suppliable
argument (CLAUDE.md "Architecture Invariants").

Runs alongside the existing /ask-query (pal_qa.answer_financial_question)
without touching it -- see app.py's AGENT_QUERY_ENGINE_ENABLED flag.
"""
from __future__ import annotations

import uuid

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import build_agent_graph
from agent.memory import get_checkpointer
from agent.tools import build_tools


def chat(question: str, user_id: str, company_name: str, thread_id: str | None = None) -> dict:
    """Runs one turn of the conversational agent.

    Returns a dict with `success`, `answer`, `evidence`, `thread_id`. Raises
    llm_client.LLMUnavailableError if no cloud LLM provider is configured
    (there is no local fallback -- see llm_client.py's PRIVACY TRADE-OFF note).
    """
    thread_id = thread_id or f"{user_id}:{uuid.uuid4().hex}"

    tools, evidence = build_tools(user_id=user_id, company_name=company_name)
    checkpointer = get_checkpointer()
    graph = build_agent_graph(tools, checkpointer, company_name=company_name)

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [HumanMessage(content=question)]}, config=config)

    final = result["messages"][-1]
    answer_text = final.content if isinstance(final, AIMessage) else str(getattr(final, "content", ""))

    return {
        "success": True,
        "answer": answer_text,
        "evidence": evidence,
        "thread_id": thread_id,
    }
