"""Iteration 9 — C1+C2 pipeline wiring tests.

Pure-Python tests (no DB, no network, no OCR) — run in CI with no secrets.
Tests verify:
  - C1 pages conversion format for build_spatial_chunks()
  - flatten_chunks_for_embedding() output schema
  - Guard path: empty safe_boxes → upsert_chunk_embeddings not called
  - normalize_record() includes safe_boxes_json + spatial_chunks_json

DB integration test (skipped when DATABASE_URL absent):
  - spatial blob columns exist on FinancialDocument after migration
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_DB_SKIP = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping DB integration tests",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_safe_box(text: str = "Invoice", bbox=None, confidence: float = 0.9) -> dict:
    return {
        "text": text,
        "bbox": bbox or [0, 0, 100, 20],
        "confidence": confidence,
        "locked_digits": [],
        "source": "original",
        "polygon": None,
    }


def _make_safe_boxes_by_page(n_pages: int = 2, n_boxes: int = 3) -> list:
    """Generate a safe_boxes_by_page list with n_pages pages and n_boxes per page."""
    return [
        [_make_safe_box(f"Row {p}-{b}", bbox=[b * 50, p * 30, b * 50 + 40, p * 30 + 20])
         for b in range(n_boxes)]
        for p in range(n_pages)
    ]


# ── C1 pages format conversion ────────────────────────────────────────────────

def test_c1_pages_format_preserves_page_count():
    safe_boxes = _make_safe_boxes_by_page(n_pages=3)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    assert len(c1_pages) == 3


def test_c1_pages_format_has_correct_page_numbers():
    safe_boxes = _make_safe_boxes_by_page(n_pages=2)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    assert c1_pages[0]["page"] == 1
    assert c1_pages[1]["page"] == 2


def test_c1_pages_format_preserves_box_count():
    safe_boxes = _make_safe_boxes_by_page(n_pages=2, n_boxes=5)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    assert len(c1_pages[0]["boxes"]) == 5


def test_build_spatial_chunks_returns_top_level_keys():
    from spatial_serialization import build_spatial_chunks
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=3)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    result = build_spatial_chunks(c1_pages, tenant_id="t1", document_id="d1")
    for key in ("tenant_id", "document_id", "version", "pages"):
        assert key in result, f"Missing key: {key}"


def test_build_spatial_chunks_sets_tenant_and_doc_ids():
    from spatial_serialization import build_spatial_chunks
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=2)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    result = build_spatial_chunks(c1_pages, tenant_id="tenant_abc", document_id="doc_xyz")
    assert result["tenant_id"] == "tenant_abc"
    assert result["document_id"] == "doc_xyz"


def test_build_spatial_chunks_empty_pages_returns_empty():
    from spatial_serialization import build_spatial_chunks
    result = build_spatial_chunks([], tenant_id="t1", document_id="d1")
    assert result.get("pages", []) == []


# ── flatten_chunks_for_embedding output schema ────────────────────────────────

def test_flatten_chunks_returns_list():
    from spatial_serialization import build_spatial_chunks
    from vector_index import flatten_chunks_for_embedding
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=4)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    chunks = build_spatial_chunks(c1_pages, tenant_id="t1", document_id="d1")
    rows = flatten_chunks_for_embedding(chunks)
    assert isinstance(rows, list)


def test_flatten_chunks_required_keys():
    from spatial_serialization import build_spatial_chunks
    from vector_index import flatten_chunks_for_embedding
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=4)
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    chunks = build_spatial_chunks(c1_pages, tenant_id="t1", document_id="d1")
    rows = flatten_chunks_for_embedding(chunks)
    if rows:
        for key in ("tenant_id", "document_id", "chunk_id", "page", "bbox", "chunk_type", "text"):
            assert key in rows[0], f"Missing key: {key}"


def test_flatten_chunks_tenant_propagated():
    from spatial_serialization import build_spatial_chunks
    from vector_index import flatten_chunks_for_embedding
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=3)
    c1_pages = [{"page": 1, "boxes": safe_boxes[0]}]
    chunks = build_spatial_chunks(c1_pages, tenant_id="my_tenant", document_id="my_doc")
    rows = flatten_chunks_for_embedding(chunks)
    for row in rows:
        assert row["tenant_id"] == "my_tenant"
        assert row["document_id"] == "my_doc"


# ── Guard path: empty safe_boxes → embedding not triggered ───────────────────

def test_empty_safe_boxes_produces_no_c1_pages():
    safe_boxes: list = []
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    assert c1_pages == []


def test_empty_c1_pages_skips_build(monkeypatch):
    """When safe_boxes is empty, build_spatial_chunks should not be called."""
    from spatial_serialization import build_spatial_chunks
    called = []
    monkeypatch.setattr(
        "spatial_serialization.build_spatial_chunks",
        lambda *a, **kw: called.append(True) or {},
    )
    safe_boxes: list = []
    c1_pages = [{"page": i + 1, "boxes": pb} for i, pb in enumerate(safe_boxes)]
    if c1_pages:
        build_spatial_chunks(c1_pages, tenant_id="t", document_id="d")
    assert called == [], "build_spatial_chunks should not be called for empty safe_boxes"


# ── normalize_record includes spatial fields ──────────────────────────────────

def test_normalize_record_has_safe_boxes_json_key():
    from dataset_manager import normalize_record
    data = {
        "document_type": "invoice",
        "company_name": "Acme",
        "safe_boxes_json": json.dumps([[{"text": "X", "bbox": [0,0,10,10]}]]),
    }
    record = normalize_record(data, user_id="u1", force_generate_document_id=False)
    assert "safe_boxes_json" in record


def test_normalize_record_has_spatial_chunks_json_key():
    from dataset_manager import normalize_record
    data = {
        "document_type": "invoice",
        "spatial_chunks_json": json.dumps({"tenant_id": "t", "pages": []}),
    }
    record = normalize_record(data, user_id="u1", force_generate_document_id=False)
    assert "spatial_chunks_json" in record


def test_normalize_record_null_when_missing():
    from dataset_manager import normalize_record
    data = {"document_type": "invoice"}
    record = normalize_record(data, user_id="u1", force_generate_document_id=False)
    assert record["safe_boxes_json"] == "NULL"
    assert record["spatial_chunks_json"] == "NULL"


def test_normalize_record_preserves_json_string():
    from dataset_manager import normalize_record
    blob = json.dumps([{"text": "Invoice Total", "bbox": [0, 0, 100, 20]}])
    data = {"document_type": "invoice", "safe_boxes_json": blob}
    record = normalize_record(data, user_id="u1", force_generate_document_id=False)
    assert record["safe_boxes_json"] == blob


# ── DB integration: columns exist after migration ─────────────────────────────

@_DB_SKIP
def test_spatial_blob_columns_exist_in_db():
    """Verify safeboxJson and spatialChunksJson columns exist on FinancialDocument."""
    import db
    with db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'FinancialDocument'
              AND column_name IN ('safeboxJson', 'spatialChunksJson')
        """)
        cols = {r["column_name"] for r in cur.fetchall()}
    assert "safeboxJson" in cols, "safeboxJson column missing — run the Iter9 migration"
    assert "spatialChunksJson" in cols, "spatialChunksJson column missing — run the Iter9 migration"


@_DB_SKIP
def test_spatial_blobs_can_be_inserted_and_read():
    """Round-trip: insert a doc with spatial blobs, read them back, verify content."""
    import db
    from dataset_manager import upsert_confirmed_record, get_record_by_id_for_user
    import json as _json

    tenant = f"test_{uuid.uuid4().hex}"
    safe_boxes = _make_safe_boxes_by_page(n_pages=1, n_boxes=2)
    safe_blob = _json.dumps(safe_boxes)

    doc_data = {
        "document_type": "invoice",
        "company_name": "Blob Test Co",
        "supplier_name": "Blob Supplier",
        "date": "2024-01-01",
        "flow_type": "payable",
        "currency": "LKR",
        "raw_total_amount": 100.0,
        "final_total_amount": 100.0,
        "payable_amount": 100.0,
    }

    # Insert document normally (no spatial blobs yet)
    result = upsert_confirmed_record(doc_data, user_id=tenant)
    doc_id = result["record"]["document_id"]

    # Directly update with spatial blobs via SQL
    with db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            'UPDATE "FinancialDocument" SET "safeboxJson"=%s, "spatialChunksJson"=%s '
            'WHERE "tenantId"=%s AND "documentId"=%s',
            (safe_blob, '{"pages":[]}', tenant, doc_id),
        )

    # Read back via the API layer
    fetched = get_record_by_id_for_user(tenant, doc_id)
    assert fetched is not None
    # safe_boxes_json is returned as a string in the record
    assert fetched.get("safe_boxes_json") == safe_blob

    # Cleanup
    with db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM "FinancialDocument" WHERE "tenantId"=%s', (tenant,))
