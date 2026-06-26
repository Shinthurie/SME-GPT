-- Run this in Supabase SQL Editor to add columns that were created in
-- Iterations 17 & 18 but may not exist in your Supabase instance yet.
-- All columns are optional (nullable) so existing documents are unaffected.

ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fileSizeKb"        FLOAT;
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fieldChunkMapJson"  TEXT;
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "safeboxJson"        TEXT;
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "spatialChunksJson"  TEXT;
