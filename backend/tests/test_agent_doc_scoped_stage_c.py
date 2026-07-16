"""Phase 3 Stage C — document-scoped chat ("Ask about this document").

Covers: build_agent_graph injecting the current-document context into the
system prompt, record_turn tagging chat_thread.document_id (set-once via
COALESCE), and service.chat threading document_id end to end.

Hermetic: scripted fake tool-calling model + fake DB cursor.
"""
from __future__ import annotations

import pandas as pd
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

import agent.graph as agent_graph
import agent.service as agent_service
import agent.threads as threads_mod
from langgraph.checkpoint.memory import MemorySaver


class ScriptedToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class RecordingModel(ScriptedToolCallingModel):
    """Captures the system prompt the graph passes on invoke, so we can assert
    the document context reached the model."""
    seen: dict = {}

    def invoke(self, messages, *args, **kwargs):
        RecordingModel.seen["system"] = str(messages[0].content)
        return super().invoke(messages, *args, **kwargs)


# ---------------------------------------------------------------------------
# graph: document context in the system prompt
# ---------------------------------------------------------------------------

def test_build_agent_graph_injects_document_context(monkeypatch):
    RecordingModel.seen = {}
    model = RecordingModel(responses=[AIMessage(content="This invoice totals LKR 5,000.")])
    monkeypatch.setattr(agent_graph, "get_chat_model", lambda temperature=0.0: model)

    graph = agent_graph.build_agent_graph([], MemorySaver(), company_name="AIESEC", document_id="IN11")
    graph.invoke({"messages": [HumanMessage(content="what is this document?")]},
                 config={"configurable": {"thread_id": "t1"}})

    assert "IN11" in RecordingModel.seen["system"]
    assert "CURRENT DOCUMENT" in RecordingModel.seen["system"]


def test_build_agent_graph_no_document_context_when_unscoped(monkeypatch):
    RecordingModel.seen = {}
    model = RecordingModel(responses=[AIMessage(content="Hi!")])
    monkeypatch.setattr(agent_graph, "get_chat_model", lambda temperature=0.0: model)

    graph = agent_graph.build_agent_graph([], MemorySaver(), company_name="AIESEC")
    graph.invoke({"messages": [HumanMessage(content="hi")]},
                 config={"configurable": {"thread_id": "t1"}})

    assert "CURRENT DOCUMENT" not in RecordingModel.seen["system"]


# ---------------------------------------------------------------------------
# threads: record_turn tags document_id (set-once)
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self):
        self.executed = []
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


def _fake_get_conn(cur):
    from contextlib import contextmanager

    class _Conn:
        def cursor(self_inner):
            return cur

    @contextmanager
    def get_conn():
        yield _Conn()

    return get_conn


def test_record_turn_persists_document_id_with_coalesce(monkeypatch):
    cur = _FakeCursor()
    monkeypatch.setattr(threads_mod, "get_conn", _fake_get_conn(cur))

    threads_mod.record_turn(
        thread_id="u1:t1", user_id="u1", company_name="AIESEC",
        question="what is this?", answer="An invoice.", document_id="IN11",
    )

    thread_sql, params = cur.executed[0]
    assert "document_id" in thread_sql
    assert "COALESCE(chat_thread.document_id, EXCLUDED.document_id)" in thread_sql
    assert "IN11" in params


# ---------------------------------------------------------------------------
# service.chat: document_id flows through to graph + record_turn
# ---------------------------------------------------------------------------

def test_chat_threads_document_id_end_to_end(monkeypatch):
    monkeypatch.setattr("agent.tools.resolve_scope_with_c4",
                        lambda company, user: (pd.DataFrame(), "No records found."))

    model = ScriptedToolCallingModel(responses=[AIMessage(content="It's invoice IN11.")])
    monkeypatch.setattr(agent_graph, "get_chat_model", lambda temperature=0.0: model)
    monkeypatch.setattr(agent_service, "get_checkpointer", lambda: MemorySaver())

    recorded: dict = {}
    monkeypatch.setattr(agent_service, "record_turn", lambda **kw: recorded.update(kw))

    # Spy on build_agent_graph (as imported into service) to confirm document_id
    # is threaded through, then delegate to the real builder.
    seen: dict = {}
    orig_build = agent_service.build_agent_graph

    def spy_build(tools, checkpointer, company_name, document_id=None):
        seen["document_id"] = document_id
        return orig_build(tools, checkpointer, company_name=company_name, document_id=document_id)

    monkeypatch.setattr(agent_service, "build_agent_graph", spy_build)

    result = agent_service.chat(
        question="what is this document?", user_id="u1", company_name="AIESEC", document_id="IN11",
    )

    assert seen["document_id"] == "IN11"
    assert recorded["document_id"] == "IN11"
    assert result["success"] is True
