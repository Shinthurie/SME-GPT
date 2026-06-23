-- Iteration 18 GAP-18C: field→chunk ID map for click-to-source provenance
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fieldChunkMapJson" TEXT;
