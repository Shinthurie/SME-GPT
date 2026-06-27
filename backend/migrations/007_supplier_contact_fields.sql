-- Migration 007: Supplier/customer contact fields (city, phone, email)
-- Fixes: "Suppliers from Colombo", "Show supplier contact details",
--        "Which supplier has overdue invoices?" (cross-reference query support)
-- Run with: python backend/scripts/run_migration.py backend/migrations/007_supplier_contact_fields.sql

ALTER TABLE "FinancialDocument"
  ADD COLUMN IF NOT EXISTS "supplierCity"    TEXT,
  ADD COLUMN IF NOT EXISTS "supplierPhone"   TEXT,
  ADD COLUMN IF NOT EXISTS "supplierEmail"   TEXT,
  ADD COLUMN IF NOT EXISTS "companyCity"     TEXT,
  ADD COLUMN IF NOT EXISTS "companyPhone"    TEXT,
  ADD COLUMN IF NOT EXISTS "companyEmail"    TEXT;

-- Indexes to support city-based supplier lookups
CREATE INDEX IF NOT EXISTS "idx_fd_supplier_city"
  ON "FinancialDocument" ("tenantId", "supplierCity")
  WHERE "deletedAt" IS NULL;
