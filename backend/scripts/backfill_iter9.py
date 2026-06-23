"""
Backfill script — Iteration 18 GAP-18E

Populates spatialChunksJson, safeboxJson, fileSizeKb, and ChunkEmbedding rows
for documents saved before Iteration 9 (which introduced spatial chunk storage).

Usage:
    cd backend
    python scripts/backfill_iter9.py               # process all docs for all users
    python scripts/backfill_iter9.py --dry-run     # list docs needing backfill, no writes
    python scripts/backfill_iter9.py --user <id>   # restrict to one tenant
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Allow importing backend modules from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_conn


def _docs_needing_backfill(user_id: str | None = None) -> list[dict]:
    where = ['"deletedAt" IS NULL', '"spatialChunksJson" IS NULL']
    params: list = []
    if user_id:
        where.append('"tenantId" = %s')
        params.append(str(user_id))
    sql = f'SELECT "id", "tenantId", "documentId", "correctedText", "rawText" FROM "FinancialDocument" WHERE {" AND ".join(where)} ORDER BY "createdAt" DESC'
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return list(cur.fetchall() or [])


def _backfill_one(doc: dict, dry_run: bool) -> str:
    doc_id = doc.get("documentId") or doc.get("document_id", "?")
    tenant_id = doc.get("tenantId") or doc.get("user_id", "?")
    text = doc.get("correctedText") or doc.get("rawText") or ""
    if not text.strip():
        return f"  SKIP {doc_id}: no text"

    if dry_run:
        return f"  WOULD backfill {doc_id} (tenant {tenant_id})"

    try:
        from spatial_serialization import build_spatial_chunks
        from vector_index import flatten_chunks_for_embedding, embed_rows, upsert_chunk_embeddings
        from embedding_service import get_embedding_service

        # Build minimal C1-style page structure from plain text
        fake_boxes = [{"text": line, "bbox": [0, 0, 100, 20], "confidence": 0.9, "locked_digits": False, "source": "raw_ocr"}
                      for line in text.splitlines() if line.strip()]
        c1_pages = [{"page": 1, "boxes": fake_boxes}]
        rich = build_spatial_chunks(c1_pages, tenant_id=str(tenant_id), document_id=str(doc_id))
        rows = flatten_chunks_for_embedding(rich)
        if rows:
            embedded = embed_rows(rows, service=get_embedding_service())
            upsert_chunk_embeddings(embedded)

        safe_json = json.dumps(fake_boxes, ensure_ascii=False)
        chunks_json = json.dumps(rich, ensure_ascii=False)

        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                'UPDATE "FinancialDocument" SET "safeboxJson"=%s, "spatialChunksJson"=%s, "updatedAt"=NOW() '
                'WHERE "tenantId"=%s AND "documentId"=%s AND "deletedAt" IS NULL',
                (safe_json, chunks_json, str(tenant_id), str(doc_id)),
            )
            conn.commit()
        return f"  OK  {doc_id} — {len(rows)} chunks embedded"
    except Exception as e:
        return f"  ERR {doc_id}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill spatial chunks + embeddings for pre-Iter9 documents")
    parser.add_argument("--dry-run", action="store_true", help="List documents without writing")
    parser.add_argument("--user", metavar="USER_ID", help="Restrict to a single tenant")
    args = parser.parse_args()

    docs = _docs_needing_backfill(user_id=args.user)
    print(f"Found {len(docs)} document(s) missing spatialChunksJson.")
    if not docs:
        print("Nothing to do.")
        return

    for doc in docs:
        result = _backfill_one(doc, dry_run=args.dry_run)
        print(result)

    if args.dry_run:
        print("\n[DRY RUN] No changes written. Re-run without --dry-run to apply.")
    else:
        print(f"\nBackfill complete: {len(docs)} document(s) processed.")


if __name__ == "__main__":
    main()
