-- Migration 003: Add cash flow tracking fields + category + migrate income/expense flow types
-- Run with: python backend/scripts/run_migration.py backend/migrations/003_add_cash_flow_fields.sql

-- New columns
ALTER TABLE "FinancialDocument"
  ADD COLUMN IF NOT EXISTS "cashInflowed"  FLOAT,
  ADD COLUMN IF NOT EXISTS "cashOutflowed" FLOAT,
  ADD COLUMN IF NOT EXISTS "category"      TEXT;

-- Migrate old flow type values → new values
UPDATE "FinancialDocument" SET "flowType" = 'cash_inflow'  WHERE "flowType" = 'income';
UPDATE "FinancialDocument" SET "flowType" = 'cash_outflow' WHERE "flowType" = 'expense';
UPDATE "FinancialDocument" SET "effectiveFlowType" = 'cash_inflow'  WHERE "effectiveFlowType" = 'income';
UPDATE "FinancialDocument" SET "effectiveFlowType" = 'cash_outflow' WHERE "effectiveFlowType" = 'expense';

-- Backfill category for existing records
UPDATE "FinancialDocument"
  SET "category" = 'Revenue'
  WHERE "effectiveFlowType" IN ('receivable', 'cash_inflow')
    AND "deletedAt" IS NULL;

UPDATE "FinancialDocument"
  SET "category" = 'Expenses'
  WHERE "effectiveFlowType" IN ('payable', 'cash_outflow')
    AND "deletedAt" IS NULL;
