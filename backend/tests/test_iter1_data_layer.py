"""Iteration 1 — data-access layer CRUD + tenant-isolation tests.

These hit the real Postgres/Supabase database, so they are skipped when
DATABASE_URL is not set (e.g. in CI without the secret). Each run uses unique
throwaway tenant ids and hard-deletes its rows afterwards.
"""

import os
import uuid

import pytest

# Load backend/.env so DATABASE_URL is visible to the skip check below
# (present locally, absent in CI -> tests skip). Guarded so test collection
# never fails when backend deps (dotenv) aren't installed, e.g. in CI.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
except Exception:
    pass

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping DB integration tests",
)


def _sample_data():
    return {
        "document_type": "invoice",
        "company_name": "Test Buyer Ltd",
        "supplier_name": "Test Supplier",
        "date": "2025-01-15",
        "flow_type": "payable",
        "currency": "LKR",
        "raw_total_amount": 500.0,
        "final_total_amount": 500.0,
        "payable_amount": 500.0,
        "items": [
            {"description": "Apple", "quantity": 5, "unit_price": 100.0, "line_total": 500.0},
        ],
    }


@pytest.fixture
def tenants():
    import db
    a = f"test_{uuid.uuid4().hex}"
    b = f"test_{uuid.uuid4().hex}"
    yield a, b
    # Cleanup: hard-delete everything for these test tenants (cascades line items).
    with db.get_conn() as conn:
        cur = conn.cursor()
        for t in (a, b):
            cur.execute('DELETE FROM "FinancialDocument" WHERE "tenantId" = %s', (t,))


def test_insert_and_read(tenants):
    import dataset_manager as dm
    tenant_a, _ = tenants

    result = dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)
    assert result["action"] == "inserted"
    doc_id = result["record"]["document_id"]
    assert doc_id and doc_id != "NULL"

    fetched = dm.get_record_by_id_for_user(tenant_a, doc_id)
    assert fetched is not None
    assert fetched["company_name"] == "Test Buyer Ltd"
    assert len(fetched["items"]) == 1
    assert fetched["items"][0]["description"] == "Apple"


def test_tenant_isolation(tenants):
    import dataset_manager as dm
    tenant_a, tenant_b = tenants

    inserted = dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)
    doc_id = inserted["record"]["document_id"]

    # Tenant B must not see or touch tenant A's document.
    assert dm.get_record_by_id_for_user(tenant_b, doc_id) is None
    assert dm.load_all_records(tenant_b) == []
    assert dm.update_record_for_user(tenant_b, doc_id, {"company_name": "Hacked"}) is None
    assert dm.delete_record_for_user(tenant_b, doc_id) is False

    # Tenant A still intact.
    assert dm.get_record_by_id_for_user(tenant_a, doc_id) is not None
    assert len(dm.load_all_records(tenant_a)) == 1


def test_update(tenants):
    import dataset_manager as dm
    tenant_a, _ = tenants

    doc_id = dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)["record"]["document_id"]
    updated = dm.update_record_for_user(
        tenant_a, doc_id,
        {"company_name": "Renamed Co", "items": [
            {"description": "Banana", "quantity": 2, "unit_price": 50, "line_total": 100},
        ]},
    )
    assert updated is not None
    assert updated["company_name"] == "Renamed Co"

    refetched = dm.get_record_by_id_for_user(tenant_a, doc_id)
    assert refetched["company_name"] == "Renamed Co"
    assert len(refetched["items"]) == 1
    assert refetched["items"][0]["description"] == "Banana"


def test_duplicate_detection(tenants):
    import dataset_manager as dm
    tenant_a, _ = tenants

    dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)
    again = dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)
    assert again["action"] == "duplicate_exists"


def test_soft_delete(tenants):
    import dataset_manager as dm
    tenant_a, _ = tenants

    doc_id = dm.upsert_confirmed_record(_sample_data(), user_id=tenant_a)["record"]["document_id"]
    assert dm.delete_record_for_user(tenant_a, doc_id) is True
    assert dm.get_record_by_id_for_user(tenant_a, doc_id) is None
    assert dm.load_all_records(tenant_a) == []
