import builtins
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm_correction


def test_call_ollama_raises_on_missing_requests(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ModuleNotFoundError("No module named 'requests'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match="requires the 'requests' package"):
        llm_correction.call_ollama("hello")


def test_call_ollama_uses_requests_when_available(monkeypatch):
    class DummyResponse:
        text = "ok"

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": " refined output "}}]}

    fake_requests = types.SimpleNamespace(
        post=lambda *args, **kwargs: DummyResponse(),
        exceptions=types.SimpleNamespace(
            ConnectionError=Exception,
            HTTPError=Exception,
            Timeout=Exception,
        ),
    )

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    result = llm_correction.call_ollama("hello")
    assert result == "refined output"
