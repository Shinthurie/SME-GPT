"""One-off migration: financial_documents_clean.csv -> Postgres (Supabase).

Idempotent and dry-run by default. Each CSV row is already a normalized record
(DATASET_COLUMNS), so we map it straight into FinancialDocument + LineItem.

Usage:
    python migrate_csv_to_db.py                      # dry run, default CSV
    python migrate_csv_to_db.py --apply              # actually write
    python migrate_csv_to_db.py --tenant <user_id>   # remap all rows to one tenant
    python migrate_csv_to_db.py --csv path/to.csv --apply

Note: rows keep their original user_id as tenantId unless --tenant is given.
Old user_ids may not match users in a fresh Supabase DB; use --tenant to claim
the data under a real account.
"""

import argparse
import json

import pandas as pd

import db
import dataset_manager as dm


def _exists(cur, tenant_id: str, document_id: str) -> bool:
    cur.execute(
        'SELECT 1 FROM "FinancialDocument" WHERE "tenantId" = %s AND "documentId" = %s LIMIT 1',
        (str(tenant_id), str(document_id)),
    )
    return cur.fetchone() is not None


def _insert_row(cur, record: dict, tenant_id: str):
    doc_pk = db.new_id("fd")
    db_values = {"id": doc_pk}
    for rec_key, db_col in dm.RECORD_TO_DB.items():
        value = tenant_id if rec_key == "user_id" else record.get(rec_key)
        db_values[db_col] = dm._record_to_db_value(rec_key, value)

    columns = list(db_values.keys())
    col_sql = ", ".join(f'"{c}"' for c in columns) + ', "updatedAt"'
    placeholders = ", ".join(["%s"] * len(columns)) + ", NOW()"
    cur.execute(
        f'INSERT INTO "FinancialDocument" ({col_sql}) VALUES ({placeholders})',
        list(db_values.values()),
    )

    try:
        items = dm.normalize_items(json.loads(record.get("items_json") or "[]"))
    except Exception:
        items = []
    dm._insert_line_items(cur, doc_pk, tenant_id, record.get("currency"), items)


def migrate(csv_path: str, tenant_override: str = None, apply: bool = False):
    df = pd.read_csv(csv_path, keep_default_na=False)
    for col in dm.DATASET_COLUMNS:
        if col not in df.columns:
            df[col] = "NULL"

    total = len(df)
    inserted = skipped = 0

    with db.get_conn() as conn:
        cur = conn.cursor()
        for _, row in df.iterrows():
            record = {c: row[c] for c in dm.DATASET_COLUMNS}
            tenant_id = tenant_override or record.get("user_id")
            document_id = record.get("document_id")

            if not tenant_id or str(tenant_id).strip().upper() == "NULL":
                print(f"  SKIP (no tenant): doc={document_id}")
                skipped += 1
                continue

            if _exists(cur, tenant_id, document_id):
                skipped += 1
                continue

            if apply:
                _insert_row(cur, record, str(tenant_id))
            inserted += 1
            print(f"  {'INSERT' if apply else 'WOULD INSERT'}: tenant={tenant_id} doc={document_id}")

        if not apply:
            conn.rollback()  # ensure dry-run writes nothing

    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total} rows | "
          f"{inserted} {'inserted' if apply else 'to insert'} | {skipped} skipped (existing/no-tenant)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Migrate CSV financial documents into Postgres.")
    ap.add_argument("--csv", default="financial_documents_clean.csv")
    ap.add_argument("--tenant", default=None, help="Override tenant_id for all rows")
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry run)")
    args = ap.parse_args()
    migrate(args.csv, tenant_override=args.tenant, apply=args.apply)
