-- Iteration 16/17: store uploaded file size per document
ALTER TABLE "FinancialDocument" ADD COLUMN IF NOT EXISTS "fileSizeKb" DOUBLE PRECISION;
