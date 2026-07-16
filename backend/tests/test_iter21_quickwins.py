"""Tests for Iteration 21 quick wins:

- IT-28: JSON output mode in the extraction LLM call.
- IT-21: upload-date range filter on load_records / count_records.

All hermetic — the LLM HTTP call and the DB connection are faked. Local Ollama
inference has been removed; the query/pipeline tiers route to DeepSeek here.
"""
from __future__ import annotations

from datetime import datetime


# ──────────────────────────── IT-28: DeepSeek JSON mode ──────────────────────

def _fake_requests_post(captured):
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "{}"}}]}
        text = ""

    def _post(url, json=None, timeout=None, headers=None):  # noqa: A002 - mirror requests API
        captured.append(json)
        return FakeResponse()

    return _post


def test_call_llm_passes_json_format(monkeypatch):
    """format='json' must be forwarded to DeepSeek as response_format json_object."""
    import llm_client
    captured: list = []
    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "QUERY_PROVIDER", "deepseek")
    monkeypatch.setattr(llm_client.requests, "post", _fake_requests_post(captured))

    llm_client.call_llm("hi", system="sys", format="json")

    assert captured, "DeepSeek was not called"
    assert captured[0].get("response_format") == {"type": "json_object"}


def test_call_llm_omits_format_by_default(monkeypatch):
    """Without an explicit format, no 'response_format' key should be sent (free-form text)."""
    import llm_client
    captured: list = []
    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "QUERY_PROVIDER", "deepseek")
    monkeypatch.setattr(llm_client.requests, "post", _fake_requests_post(captured))

    llm_client.call_llm("hi")

    assert captured
    assert "response_format" not in captured[0]


def test_extractor_uses_json_format(monkeypatch):
    """ocr_to_json_extractor.extract_via_llm must request JSON output mode (IT-28)."""
    import ocr_to_json_extractor as ex
    captured: dict = {}

    def fake_call_pipeline_llm(prompt, system="", format=None):
        captured["format"] = format
        return "{}"

    monkeypatch.setattr(ex, "call_pipeline_llm", fake_call_pipeline_llm)
    ex.extract_via_llm("some prompt")

    assert captured.get("format") == "json"


# ──────────────────────────── IT-21: date-range filter ───────────────────────

def test_parse_date_bounds_inclusive_upper():
    """date_to is made inclusive by advancing the upper bound to the next day."""
    import dataset_manager as dm
    lower, upper = dm.parse_date_bounds("2026-03-01", "2026-03-31")
    assert lower == datetime(2026, 3, 1)
    assert upper == datetime(2026, 4, 1)  # start of day AFTER date_to


def test_parse_date_bounds_handles_missing_and_invalid():
    import dataset_manager as dm
    assert dm.parse_date_bounds(None, None) == (None, None)
    assert dm.parse_date_bounds("", "") == (None, None)
    assert dm.parse_date_bounds("not-a-date", "2026/03/31") == (None, None)


class _FakeCursor:
    def __init__(self, sink): self.sink = sink
    def execute(self, sql, params=()):
        self.sink["sql"].append(sql)
        self.sink["params"].append(list(params))
    def fetchall(self): return []
    def fetchone(self): return {"n": 0}


class _FakeConn:
    def __init__(self, sink): self.sink = sink
    def cursor(self): return _FakeCursor(self.sink)
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_load_records_date_filter_no_sql_clause(monkeypatch):
    """load_records does NOT add a docDate SQL clause — filtering is done in Python."""
    import dataset_manager as dm
    sink = {"sql": [], "params": []}
    monkeypatch.setattr(dm, "get_conn", lambda: _FakeConn(sink))

    dm.load_records(user_id="u1", date_from="2026-03-01", date_to="2026-03-31")

    sql = sink["sql"][0]
    # SQL should NOT contain docDate — Python-side filter handles it
    assert '"docDate" >=' not in sql
    assert '"docDate" <' not in sql
    # But it must still filter by tenantId
    assert '"tenantId"' in sql


def test_load_records_no_date_filter_omits_clause(monkeypatch):
    import dataset_manager as dm
    sink = {"sql": [], "params": []}
    monkeypatch.setattr(dm, "get_conn", lambda: _FakeConn(sink))

    dm.load_records(user_id="u1")

    assert '"docDate"' not in sink["sql"][0]


def test_count_records_date_filter_python_side(monkeypatch):
    """count_records with date range fetches docDate column and filters in Python."""
    import dataset_manager as dm
    sink = {"sql": [], "params": []}
    monkeypatch.setattr(dm, "get_conn", lambda: _FakeConn(sink))

    total = dm.count_records("u1", date_from="2026-03-01", date_to="2026-03-31")

    assert total == 0   # FakeConn returns empty rows
    sql = sink["sql"][0]
    # It fetches documentId + docDate, not COUNT(*)
    assert '"docDate"' in sql
    assert "%s" in sql
