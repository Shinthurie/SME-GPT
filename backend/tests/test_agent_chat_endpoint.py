"""POST /chat — Phase 1 agentic query engine endpoint.

Feature-flagged (AGENT_QUERY_ENGINE_ENABLED, default off) alongside the
existing /ask-query. Tested against the real FastAPI app via TestClient, same
pattern as test_iter12_gdpr_endpoints.py; agent.service.chat is monkeypatched
so no real LLM/DB is needed.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass


@pytest.fixture(scope="module")
def app_module():
    import app as app_mod
    return app_mod


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app, raise_server_exceptions=False)


def _token(app_module, **claims):
    import jwt as pyjwt
    return pyjwt.encode(claims, app_module.JWT_SECRET, algorithm=app_module.JWT_ALGORITHM)


def _bearer(app_module, **claims):
    return f"Bearer {_token(app_module, **claims)}"


def test_chat_disabled_by_default_returns_503(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_QUERY_ENGINE_ENABLED", False)
    resp = client.post(
        "/chat",
        json={"company_name": "AIESEC", "question": "hello"},
        headers={"Authorization": _bearer(app_module, userId="u1", role="owner")},
    )
    assert resp.status_code == 503


def test_chat_requires_auth(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_QUERY_ENGINE_ENABLED", True)
    resp = client.post("/chat", json={"company_name": "AIESEC", "question": "hello"})
    assert resp.status_code == 401


def test_chat_requires_company_name(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_QUERY_ENGINE_ENABLED", True)
    resp = client.post(
        "/chat",
        json={"company_name": "  ", "question": "hello"},
        headers={"Authorization": _bearer(app_module, userId="u1", role="owner")},
    )
    assert resp.status_code == 400


def test_chat_enabled_returns_agent_answer(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_QUERY_ENGINE_ENABLED", True)

    import agent.service as agent_service

    def fake_chat(question, user_id, company_name, thread_id=None):
        assert user_id == "u1"
        assert company_name == "AIESEC"
        return {
            "success": True,
            "answer": "Hello! How can I help with AIESEC's finances?",
            "evidence": [],
            "thread_id": "u1:abc123",
        }

    monkeypatch.setattr(agent_service, "chat", fake_chat)

    resp = client.post(
        "/chat",
        json={"company_name": "AIESEC", "question": "hello"},
        headers={"Authorization": _bearer(app_module, userId="u1", role="owner")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "AIESEC" in body["answer"]
    assert body["thread_id"] == "u1:abc123"
    assert body["evidence"] == []


def test_chat_returns_503_when_llm_unavailable(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_QUERY_ENGINE_ENABLED", True)

    import agent.service as agent_service
    from llm_client import LLMUnavailableError

    def fake_chat(question, user_id, company_name, thread_id=None):
        raise LLMUnavailableError("no provider configured")

    monkeypatch.setattr(agent_service, "chat", fake_chat)

    resp = client.post(
        "/chat",
        json={"company_name": "AIESEC", "question": "hello"},
        headers={"Authorization": _bearer(app_module, userId="u1", role="owner")},
    )
    assert resp.status_code == 503
