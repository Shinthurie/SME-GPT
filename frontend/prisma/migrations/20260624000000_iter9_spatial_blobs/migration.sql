-- Iteration 9: persist safe_boxes and spatial_chunks per confirmed document (FR-13, FR-23)
-- Applied via psycopg (not Prisma CLI) because PgBouncer transaction mode blocks DDL.

ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "safeboxJson"       TEXT;
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "spatialChunksJson" TEXT;
