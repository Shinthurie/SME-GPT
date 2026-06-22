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

        def raise_for_status(self):
            return None

        def json(self):
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


def test_call_ollama_handles_timeout(monkeypatch):
    class ConnectionErrorForTest(Exception):
        pass

    class HttpErrorForTest(Exception):
        pass

    class TimeoutErrorForTest(Exception):
        pass

    def raise_timeout(*args, **kwargs):
        raise TimeoutErrorForTest()

    fake_requests = types.SimpleNamespace(
        post=raise_timeout,
        exceptions=types.SimpleNamespace(
            ConnectionError=ConnectionErrorForTest,
            HTTPError=HttpErrorForTest,
            Timeout=TimeoutErrorForTest,
        ),
    )

    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    with pytest.raises(Exception, match="timed out"):
        llm_correction.call_ollama("hello")
