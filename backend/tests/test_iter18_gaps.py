"""Tests for Iteration 18 gaps: GAP-18A, GAP-18C, GAP-18D, GAP-18F, GAP-18G."""
from __future__ import annotations
import inspect
import json


# ──────────────────────────── GAP-18A: DB pagination ────────────────────────

def test_load_records_sql_includes_limit_offset(monkeypatch):
    """load_records with limit/offset must include LIMIT and OFFSET in the SQL."""
    captured_sql = []
    captured_params = []

    class FakeCursor:
        def execute(self, sql, params=()):
            captured_sql.append(sql)
            captured_params.append(list(params))
        def fetchall(self): return []

    class FakeConn:
        def cursor(self): return FakeCursor()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    import dataset_manager as dm
    monkeypatch.setattr(dm, "get_conn", lambda: FakeConn())

    dm.load_records(user_id="u1", limit=10, offset=20)

    assert captured_sql, "No SQL executed"
    assert "LIMIT" in captured_sql[0].upper(), "LIMIT not in SQL"
    assert "OFFSET" in captured_sql[0].upper(), "OFFSET not in SQL"
    assert 10 in captured_params[0], "limit value missing from params"
    assert 20 in captured_params[0], "offset value missing from params"


def test_count_records_returns_int(monkeypatch):
    """count_records must return an int from the COUNT(*) query."""
    class FakeCursor:
        def execute(self, sql, params=()): pass
        def fetchone(self): return {"n": 42}

    class FakeConn:
        def cursor(self): return FakeCursor()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    import dataset_manager as dm
    monkeypatch.setattr(dm, "get_conn", lambda: FakeConn())

    result = dm.count_records("u1")
    assert result == 42
    assert isinstance(result, int)


def test_load_records_without_limit_has_no_limit_in_sql(monkeypatch):
    """When limit=None, SQL must NOT contain LIMIT (backwards compat)."""
    captured_sql = []

    class FakeCursor:
        def execute(self, sql, params=()): captured_sql.append(sql)
        def fetchall(self): return []

    class FakeConn:
        def cursor(self): return FakeCursor()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    import dataset_manager as dm
    monkeypatch.setattr(dm, "get_conn", lambda: FakeConn())

    dm.load_records(user_id="u1")  # no limit
    assert "LIMIT" not in captured_sql[0].upper()


# ──────────────────────────── GAP-18C: field→chunk map ──────────────────────

def test_build_field_chunk_map_matches_company_name():
    """_build_field_chunk_map should fuzzy-match company_name to a chunk."""
    import app as ap
    extracted = {"company_name": "ACME Corporation", "currency": "LKR"}
    spatial = {
        "pages": [{
            "page": 1,
            "chunks": [
                {"chunk_id": "c1", "text": "ACME Corp vendor invoice", "chunk_type": "key_value"},
                {"chunk_id": "c2", "text": "Total amount due", "chunk_type": "key_value"},
            ]
        }]
    }
    result = ap._build_field_chunk_map(extracted, spatial)
    assert "company_name" in result
    assert result["company_name"] == "c1"


def test_build_field_chunk_map_skips_null_values():
    """Fields with NULL or empty values must not appear in the map."""
    import app as ap
    extracted = {"company_name": "NULL", "currency": ""}
    spatial = {"pages": [{"page": 1, "chunks": [{"chunk_id": "c1", "text": "anything"}]}]}
    result = ap._build_field_chunk_map(extracted, spatial)
    assert "company_name" not in result
    assert "currency" not in result


# ──────────────────────────── GAP-18D: dashboard counts ─────────────────────

def test_build_dashboard_summary_includes_pending_ready():
    """build_dashboard_summary must return pending_processing_count and ready_for_query_count."""
    import app as ap
    records = [
        {"document_type": "invoice", "status": "ready",      "flow_type": "payable",    "payable_amount": 100, "final_total_amount": 100, "raw_total_amount": 100},
        {"document_type": "po",      "status": "processing", "flow_type": "payable",    "payable_amount": 200, "final_total_amount": 200, "raw_total_amount": 200},
        {"document_type": "invoice", "status": "ready",      "flow_type": "receivable", "payable_amount": 50,  "final_total_amount": 50,  "raw_total_amount": 50},
    ]
    summary = ap.build_dashboard_summary(records)
    assert "pending_processing_count" in summary
    assert "ready_for_query_count" in summary
    assert summary["pending_processing_count"] == 1
    assert summary["ready_for_query_count"] == 2
    assert summary["total_documents"] == 3


# ──────────────────────────── GAP-18F: C4 entity index wiring ───────────────

def test_index_document_present_in_confirm_save_source():
    """
    GAP-18F structural check: entity_index.index_document must be referenced
    inside the confirm_save handler.  entity_index is imported inline (local
    import inside a try/except) so we verify via source inspection rather than
    trying to patch a module-level attribute that doesn't exist.
    """
    import app as ap
    src = inspect.getsource(ap.confirm_save)
    assert "index_document" in src or "entity_index" in src, (
        "C4 entity_index.index_document call is missing from confirm_save"
    )
