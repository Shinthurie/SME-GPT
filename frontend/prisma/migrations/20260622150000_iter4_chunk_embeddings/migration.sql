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

-- EnableRowLevelSecurity (every other public table has RLS enabled with no
-- policies -- access control happens at the app layer via the backend's
-- privileged DATABASE_URL connection, which bypasses RLS as table owner;
-- this blocks anon/authenticated PostgREST access by default, matching the
-- existing tables exactly)
ALTER TABLE "ChunkEmbedding" ENABLE ROW LEVEL SECURITY;
