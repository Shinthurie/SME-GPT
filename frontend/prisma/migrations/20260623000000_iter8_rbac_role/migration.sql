-- Iteration 8: RBAC role field (FR-32)
-- Adds UserRole enum and role column to User; defaults all existing rows to 'owner'.

CREATE TYPE "UserRole" AS ENUM ('owner', 'accountant', 'admin', 'auditor');

ALTER TABLE "User" ADD COLUMN "role" "UserRole" NOT NULL DEFAULT 'owner';
