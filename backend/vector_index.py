"""Vector indexing & retrieval over Component-2 SpatialChunks (Iteration 4).

Embeds each SpatialChunk's `text` (from `spatial_serialization.build_spatial_chunks()` output) via
an `EmbeddingService` and stores it in the `ChunkEmbedding` table (pgvector; proposed in
docs/design/iter-4-schema.md) with tenant/document/chunk metadata + bbox provenance carried
straight from the chunk's `provenance` block (FR-14, FR-15). Retrieval does a single pgvector
cosine-distance query, filtered by tenant (and optionally one document), returning chunks ranked
by similarity with their original provenance intact (FR-16, FR-17).

DB-touching functions (`upsert_chunk_embeddings`, `retrieve_top_k`) need a real Postgres
connection (`db.get_conn()`) and the `ChunkEmbedding` table from docs/design/iter-4-schema.md —
same `DATABASE_URL`-skip pattern as `tests/test_iter1_data_layer.py`. The chunk-flattening and
ranking math underneath (`flatten_chunks_for_embedding`, `rank_embedded_rows`) is pure and is
unit-tested without a DB, using `HashingEmbeddingService` so the suite stays hermetic.

Not wired into any FastAPI endpoint yet — same "standalone, tested module" status as C1/C2; the
live pipeline still doesn't produce SpatialChunks to index (see docs/components/component-1.md /
component-2.md "Not yet wired into document_pipeline.py").
"""
from __future__ import annotations

import math

from embedding_service import EmbeddingService, get_embedding_service


def flatten_chunks_for_embedding(spatial_chunks: dict) -> list[dict]:
    """`spatial_chunks`: `build_spatial_chunks()` output. Returns one row per
    chunk: `{tenant_id, document_id, chunk_id, page, bbox, chunk_type, text}`."""
    tenant_id = spatial_chunks["tenant_id"]
    document_id = spatial_chunks["document_id"]
    rows = []
    for page in spatial_chunks.get("pages", []):
        for chunk in page.get("chunks", []):
            rows.append({
                "tenant_id": tenant_id,
                "document_id": document_id,
                "chunk_id": chunk["chunk_id"],
                "page": chunk["provenance"]["page"],
                "bbox": chunk["provenance"]["bbox"],
                "chunk_type": chunk["chunk_type"],
                "text": chunk["text"],
            })
    return rows


def embed_rows(rows: list[dict], service: EmbeddingService | None = None) -> list[dict]:
    """Attach an `embedding` (list[float]) to each row via the EmbeddingService."""
    service = service or get_embedding_service()
    if not rows:
        return []
    vectors = service.embed([r["text"] for r in rows], mode="passage")
    return [{**row, "embedding": vec} for row, vec in zip(rows, vectors)]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def rank_embedded_rows(query_vector: list[float], rows: list[dict], k: int = 5) -> list[dict]:
    """Pure, DB-free ranking: cosine similarity of `query_vector` against each
    row's `embedding`, descending, top-k. Mirrors the pgvector `<=>` query in
    `retrieve_top_k` below, so it doubles as the retrieval-hit-rate test harness
    (ROADMAP Iteration 4) without needing a live Postgres connection."""
    scored = [
        {**{key: v for key, v in row.items() if key != "embedding"},
         "similarity": _cosine_similarity(query_vector, row["embedding"])}
        for row in rows
    ]
    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return scored[:k]


def upsert_chunk_embeddings(rows: list[dict]) -> int:
    """Write embedded rows (from `embed_rows`) to the `ChunkEmbedding` table.
    Requires a real `DATABASE_URL` and the migration in
    docs/design/iter-4-schema.md to have been applied. Returns the row count."""
    import db
    from pgvector.psycopg import register_vector
    from psycopg.types.json import Json

    with db.get_conn() as conn:
        register_vector(conn)
        cur = conn.cursor()
        for row in rows:
            cur.execute(
                """
                INSERT INTO "ChunkEmbedding"
                    ("id", "tenantId", "documentId", "chunkId", "page", "bbox", "chunkType", "text", "embedding")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ("tenantId", "documentId", "chunkId")
                DO UPDATE SET "page" = EXCLUDED."page", "bbox" = EXCLUDED."bbox",
                              "chunkType" = EXCLUDED."chunkType", "text" = EXCLUDED."text",
                              "embedding" = EXCLUDED."embedding"
                """,
                (
                    db.new_id("ce"), row["tenant_id"], row["document_id"], row["chunk_id"],
                    row["page"], Json(row["bbox"]), row["chunk_type"], row["text"], row["embedding"],
                ),
            )
        return len(rows)


def retrieve_top_k(
    query: str,
    tenant_id: str,
    k: int = 5,
    document_id: str | None = None,
    service: EmbeddingService | None = None,
) -> list[dict]:
    """Embed `query` and return the top-k most similar chunks for `tenant_id`
    (optionally scoped to one `document_id`), ranked by cosine similarity,
    each with its original page/bbox/chunk_type provenance (FR-16, FR-17)."""
    service = service or get_embedding_service()
    query_vector = service.embed([query], mode="query")[0]

    import db
    from pgvector.psycopg import register_vector

    with db.get_conn() as conn:
        register_vector(conn)
        cur = conn.cursor()
        sql = """
            SELECT "chunkId" AS chunk_id, "documentId" AS document_id, "page", "bbox",
                   "chunkType" AS chunk_type, "text",
                   1 - ("embedding" <=> %s::vector) AS similarity
            FROM "ChunkEmbedding"
            WHERE "tenantId" = %s
        """
        params: list = [query_vector, tenant_id]
        if document_id:
            sql += ' AND "documentId" = %s'
            params.append(document_id)
        sql += ' ORDER BY "embedding" <=> %s::vector LIMIT %s'
        params.extend([query_vector, k])
        cur.execute(sql, params)
        return cur.fetchall()
