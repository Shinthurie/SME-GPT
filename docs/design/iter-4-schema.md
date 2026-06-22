# Iteration 4 — Vector Embeddings Schema Design

> Status: **applied** (`npx prisma migrate deploy`, 2026-06-22, migration
> `20260622150000_iter4_chunk_embeddings`) — verified live: `ChunkEmbedding` table, HNSW index, and
> RLS all present (`relrowsecurity=true`, no policies, matching every other table). Implements
> ROADMAP Iteration 4. Owner: Ashfak (vector index & retrieval is Ashfak's area per
> `WORK_DIVISION.md`); Shinthurie reviews since it touches `schema.prisma`, same as the C4 tables
> in Iteration 1.

## Goal

Add the embeddings table `docs/design/iter-1-schema.md` deferred: "pgvector deferred to Iteration
4 ... the `vector` extension is enabled now, but the embeddings table is added in Iteration 4."
This table stores one row per `SpatialChunk` (C2 output), embedded via `backend/embedding_service.py`,
so `backend/vector_index.py` can do a single pgvector cosine-distance query for retrieval (FR-14…17).

## Decisions

### 1. One row per chunk, not per document
Mirrors C2's chunk granularity (`spatial_chunks.json`) so retrieval returns individually-citable
chunks with their own `page`/`bbox`, not a whole-document blob.

### 2. `documentId` is the business id, not `FinancialDocument.id`
Matches `spatial_chunks.json`'s `document_id` field (C2's contract) directly — avoids a join just
to embed/retrieve. `tenantId` follows the same convention as every other table
(`docs/design/iter-1-schema.md` decision #2).

### 3. Embedding dimension = 384, model = `intfloat/multilingual-e5-small`
Chosen over OpenAI/Cohere hosted embeddings (avoids a second paid vendor beyond DeepSeek) and over
a general multilingual sentence-transformers model (e.g. `paraphrase-multilingual-MiniLM-L12-v2`)
because `multilingual-e5-small` is trained on mC4 (100+ languages, including Sinhala), and
embedding inference is CPU-friendly (unlike Surya v2, which needs a GPU inference backend we don't
have — see `docs/components/component-1.md`). 384-dim keeps the table and the HNSW index small.
e5 models are asymmetric: queries get a `"query: "` prefix, indexed text gets `"passage: "` (see
`backend/embedding_service.py`).

### 4. `bbox` stored as `Json`, not 4 separate columns
Matches the canonical box/chunk schema (`[x1, y1, x2, y2]`) used everywhere else in the pipeline
(`ocr_service.py`, `spatial_serialization.py`) — no reshaping needed when reading it back out for
provenance.

### 5. Manual migration SQL (Prisma `Unsupported` type)
Prisma has no native `vector` scalar; the field is declared `Unsupported("vector(384)")` and the
actual column type/index are hand-written in the migration SQL (the standard Prisma+pgvector
pattern). This migration was authored without a live DB connection (no Supabase credentials in
this environment) — apply with `npx prisma migrate deploy` against the real database, then verify
with `npx prisma db pull` that `schema.prisma` and the live schema agree.

## Proposed model (Prisma)

```prisma
model ChunkEmbedding {
  id         String   @id @default(cuid())
  tenantId   String
  documentId String                       // SpatialChunk's document_id (business id)
  chunkId    String                       // SpatialChunk.chunk_id
  page       Int
  bbox       Json                         // [x1, y1, x2, y2] — provenance.bbox
  chunkType  String                       // SpatialChunk.chunk_type
  text       String   @db.Text            // SpatialChunk.text (what's embedded)
  embedding  Unsupported("vector(384)")
  createdAt  DateTime @default(now())

  @@unique([tenantId, documentId, chunkId])
  @@index([tenantId])
  @@index([tenantId, documentId])
}
```

## Migration SQL (hand-authored, `frontend/prisma/migrations/<timestamp>_iter4_chunk_embeddings/`)

```sql
-- CreateExtension (defensive; docs/design/iter-1-schema.md says it's already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- CreateTable
CREATE TABLE "ChunkEmbedding" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "documentId" TEXT NOT NULL,
    "chunkId" TEXT NOT NULL,
    "page" INTEGER NOT NULL,
    "bbox" JSONB NOT NULL,
    "chunkType" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "embedding" vector(384) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ChunkEmbedding_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ChunkEmbedding_tenantId_idx" ON "ChunkEmbedding"("tenantId");

-- CreateIndex
CREATE INDEX "ChunkEmbedding_tenantId_documentId_idx" ON "ChunkEmbedding"("tenantId", "documentId");

-- CreateIndex
CREATE UNIQUE INDEX "ChunkEmbedding_tenantId_documentId_chunkId_key"
    ON "ChunkEmbedding"("tenantId", "documentId", "chunkId");

-- CreateIndex (approximate nearest neighbor, cosine distance)
CREATE INDEX "ChunkEmbedding_embedding_hnsw_idx"
    ON "ChunkEmbedding" USING hnsw ("embedding" vector_cosine_ops);

-- EnableRowLevelSecurity (every other public table has RLS enabled, no
-- policies -- verified live: relrowsecurity=true, relforcerowsecurity=false,
-- zero rows in pg_policies. Access control happens at the app layer via the
-- backend's privileged DATABASE_URL connection, which bypasses RLS as table
-- owner; this just blocks anon/authenticated PostgREST access by default,
-- same as every existing table)
ALTER TABLE "ChunkEmbedding" ENABLE ROW LEVEL SECURITY;
```

## Backend access pattern

Same as every other table (`docs/design/iter-1-schema.md` decision #1): Prisma is the only
migration tool; the backend reads/writes via `psycopg` (raw SQL), using the
[`pgvector`](https://github.com/pgvector/pgvector-python) Python package's `register_vector()` to
adapt Python lists to/from the `vector` column type. See `backend/vector_index.py`.

## Open questions for review

1. **HNSW vs IVFFlat index.** HNSW has better recall at small-to-medium scale and doesn't need a
   training/list-count step (`ivfflat` needs `lists` tuned to row count, which we don't have yet
   at this scale) — recommend HNSW for now, revisit if the table grows large enough that build
   time/memory becomes a problem.
2. **Re-embedding on document edit.** `PUT /documents/{id}` (existing endpoint) doesn't currently
   touch chunks/embeddings — once C1+C2 are wired into the live pipeline, edits need to
   re-run embedding for the affected chunks. Out of scope for this iteration (C1/C2 aren't wired
   into the live pipeline yet either).
3. **Cascade delete.** No FK to `FinancialDocument` is declared (different id space — business
   `documentId` vs `FinancialDocument.id`). `DELETE /documents/{id}` should also delete the
   matching `ChunkEmbedding` rows once this is wired in; tracked as a follow-up, not blocking this
   schema.
