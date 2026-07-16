-- Migration 008: chat thread registry + per-turn display history (Phase 3 Stage A)
-- Run with: python backend/scripts/run_migration.py backend/migrations/008_chat_threads.sql
--
-- The LangGraph Postgres checkpointer (checkpoints/checkpoint_* tables) remains the
-- agent's working memory; these tables are the UI-facing registry: thread listing
-- (ChatGPT-style topics), and per-turn evidence/trace snapshots for replay, which
-- the checkpointer does not store (evidence is collected out-of-band by the tools).
-- Follows query_history's conventions: snake_case columns, raw UUID text ids,
-- tenant-scoped by user_id.

CREATE TABLE IF NOT EXISTS chat_thread (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL,
    company_name          TEXT NOT NULL DEFAULT '',
    title                 TEXT NOT NULL DEFAULT '',
    last_message_preview  TEXT NOT NULL DEFAULT '',
    document_id           TEXT,           -- set when the thread is scoped to one document (Stage C)
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_thread_user
    ON chat_thread (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_message (
    id            TEXT PRIMARY KEY,
    thread_id     TEXT NOT NULL REFERENCES chat_thread (id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,
    role          TEXT NOT NULL,          -- 'user' | 'assistant'
    content       TEXT NOT NULL DEFAULT '',
    evidence      JSONB,                  -- EvidenceItem[] snapshot for this turn (assistant rows)
    trace         JSONB,                  -- tool-call trace for this turn (assistant rows)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_message_thread
    ON chat_message (thread_id, created_at ASC);
