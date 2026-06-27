-- Migration 006: PO/DN workflow status fields + invoice_status + date fields
-- Run with: python backend/scripts/run_migration.py backend/migrations/006_po_dn_workflow.sql

ALTER TABLE "FinancialDocument"
  ADD COLUMN IF NOT EXISTS "poStatus"         TEXT,
  ADD COLUMN IF NOT EXISTS "dnStatus"         TEXT,
  ADD COLUMN IF NOT EXISTS "invoiceStatus"    TEXT,
  ADD COLUMN IF NOT EXISTS "dueDate"          TEXT,
  ADD COLUMN IF NOT EXISTS "deliveryDate"     TEXT,
  ADD COLUMN IF NOT EXISTS "approvedBy"       TEXT,
  ADD COLUMN IF NOT EXISTS "proofOfDelivery"  BOOLEAN,
  ADD COLUMN IF NOT EXISTS "signed"           BOOLEAN;

-- Backfill po_status from paid_status for existing PO documents
UPDATE "FinancialDocument"
  SET "poStatus" = CASE
    WHEN "paidStatus" = 'paid'    THEN 'fulfilled'
    WHEN "paidStatus" = 'partial' THEN 'partially_delivered'
    ELSE 'pending'
  END
  WHERE "documentType" = 'po' AND "deletedAt" IS NULL AND "poStatus" IS NULL;

-- Backfill dn_status from received_status for existing DN documents
UPDATE "FinancialDocument"
  SET "dnStatus" = CASE
    WHEN "receivedStatus" = 'received' THEN 'delivered'
    WHEN "receivedStatus" = 'partial'  THEN 'partially_delivered'
    ELSE 'pending'
  END
  WHERE "documentType" = 'dn' AND "deletedAt" IS NULL AND "dnStatus" IS NULL;

-- Backfill invoice_status from paid_status for existing invoice documents
UPDATE "FinancialDocument"
  SET "invoiceStatus" = CASE
    WHEN "paidStatus" = 'paid'     THEN 'paid'
    WHEN "paidStatus" = 'partial'  THEN 'partially_paid'
    WHEN "paidStatus" = 'not_paid' THEN 'pending'
    ELSE 'pending'
  END
  WHERE "documentType" = 'invoice' AND "deletedAt" IS NULL AND "invoiceStatus" IS NULL;
