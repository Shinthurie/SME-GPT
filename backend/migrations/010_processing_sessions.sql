-- Migration 010: Persist in-progress document processing sessions
-- Replaces the in-memory PROCESSING_SESSIONS dict in app.py so a backend
-- restart between /process-document and /confirm-save no longer loses the
-- user's in-progress upload.
-- Run with: python backend/scripts/run_migration.py backend/migrations/010_processing_sessions.sql

CREATE TABLE IF NOT EXISTS processing_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_processing_sessions_user
  ON processing_sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_processing_sessions_created
  ON processing_sessions (created_at);
