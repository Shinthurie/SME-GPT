-- Migration 009: Thread query_history rows into conversations
-- Adds conversation_id so /ask-query turns can be grouped into a chat thread
-- Run with: python backend/scripts/run_migration.py backend/migrations/009_conversation_threads.sql

ALTER TABLE query_history
  ADD COLUMN IF NOT EXISTS conversation_id UUID;

CREATE INDEX IF NOT EXISTS idx_query_history_conversation
  ON query_history (user_id, conversation_id, created_at);
