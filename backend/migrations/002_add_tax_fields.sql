-- Migration 002: Add tax extraction fields to FinancialDocument
-- Run with: python backend/scripts/run_migration.py backend/migrations/002_add_tax_fields.sql

ALTER TABLE "FinancialDocument"
  ADD COLUMN IF NOT EXISTS "taxAmount" FLOAT,
  ADD COLUMN IF NOT EXISTS "taxRate"   FLOAT;
