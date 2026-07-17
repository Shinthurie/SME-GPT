"""Chat thread registry + per-turn display history (Phase 3 Stage A).

The LangGraph Postgres checkpointer remains the agent's *working memory*
(what the LLM sees on the next turn); this module is the *UI-facing* record:
ChatGPT-style thread listing with titles/previews, and per-turn snapshots of
the evidence + tool-call trace, which the checkpointer does not store (tools
collect evidence out-of-band -- see agent/tools.py build_tools).

Tenant isolation (CLAUDE.md "Architecture Invariants"): every read/write here
filters by user_id from the JWT. A thread id is only ever resolvable by its
owner; get/rename/delete on someone else's thread behaves exactly like a
missing thread.

All functions degrade gracefully when the DB is unavailable (same posture as
agent/memory.py): reads return empty, writes are dropped with a log line --
the conversation itself still works off the checkpointer.
"""
from __future__ import annotations

import json
import uuid

from db import get_conn

_TITLE_MAX = 60
_PREVIEW_MAX = 160


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def record_turn(
    thread_id: str,
    user_id: str,
    company_name: str,
    question: str,
    answer: str,
    evidence: list | None = None,
    trace: list | None = None,
    document_id: str | None = None,
) -> None:
    """Upsert the thread row (create with auto-title on first turn) and append
    the user + assistant messages for this turn. document_id tags a doc-scoped
    thread (Stage C) and is set once at creation -- COALESCE keeps the original
    so a later turn can't null it. Best-effort: a DB failure must never fail the
    chat request itself."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO chat_thread (id, user_id, company_name, title, last_message_preview, document_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET last_message_preview = EXCLUDED.last_message_preview,
                        document_id = COALESCE(chat_thread.document_id, EXCLUDED.document_id),
                        updated_at = now()
                """,
                (thread_id, str(user_id), company_name,
                 _shorten(question, _TITLE_MAX), _shorten(answer, _PREVIEW_MAX), document_id),
            )
            cur.execute(
                """
                INSERT INTO chat_message (id, thread_id, user_id, role, content)
                VALUES (%s, %s, %s, 'user', %s)
                """,
                (uuid.uuid4().hex, thread_id, str(user_id), question),
            )
            cur.execute(
                """
                INSERT INTO chat_message (id, thread_id, user_id, role, content, evidence, trace)
                VALUES (%s, %s, %s, 'assistant', %s, %s::jsonb, %s::jsonb)
                """,
                (uuid.uuid4().hex, thread_id, str(user_id), answer,
                 json.dumps(evidence or [], ensure_ascii=False, default=str),
                 json.dumps(trace or [], ensure_ascii=False, default=str)),
            )
    except Exception as exc:
        print(f"[Agent] Thread registry write failed ({exc}); conversation continues.", flush=True)


def list_threads(user_id: str) -> list[dict]:
    """Newest-first thread list for the sidebar."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, company_name, title, last_message_preview, document_id,
                       created_at, updated_at
                FROM chat_thread
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (str(user_id),),
            )
            rows = cur.fetchall()
        return [
            {
                "thread_id": r["id"],
                "company_name": r["company_name"],
                "title": r["title"],
                "last_message_preview": r["last_message_preview"],
                "document_id": r["document_id"],
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
            }
            for r in rows
        ]
    except Exception as exc:
        print(f"[Agent] Thread registry read failed ({exc}).", flush=True)
        return []


def get_thread_messages(thread_id: str, user_id: str) -> list[dict] | None:
    """Full message replay for one thread, oldest first. Returns None when the
    thread doesn't exist OR belongs to another tenant (indistinguishable on
    purpose)."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM chat_thread WHERE id = %s AND user_id = %s",
                (thread_id, str(user_id)),
            )
            if cur.fetchone() is None:
                return None
            cur.execute(
                """
                SELECT role, content, evidence, trace, created_at
                FROM chat_message
                WHERE thread_id = %s AND user_id = %s
                ORDER BY created_at ASC
                """,
                (thread_id, str(user_id)),
            )
            rows = cur.fetchall()
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "evidence": r["evidence"] or [],
                "trace": r["trace"] or [],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    except Exception as exc:
        print(f"[Agent] Thread replay read failed ({exc}).", flush=True)
        return None


def rename_thread(thread_id: str, user_id: str, title: str) -> bool:
    """Returns False when the thread doesn't exist / isn't owned by user_id."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE chat_thread SET title = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                (_shorten(title, _TITLE_MAX), thread_id, str(user_id)),
            )
            return cur.rowcount > 0
    except Exception as exc:
        print(f"[Agent] Thread rename failed ({exc}).", flush=True)
        return False


def delete_thread(thread_id: str, user_id: str) -> bool:
    """Deletes the registry rows (chat_message cascades) and best-effort clears
    the checkpointer's working memory for the thread. Returns False when the
    thread doesn't exist / isn't owned by user_id."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM chat_thread WHERE id = %s AND user_id = %s",
                (thread_id, str(user_id)),
            )
            deleted = cur.rowcount > 0
    except Exception as exc:
        print(f"[Agent] Thread delete failed ({exc}).", flush=True)
        return False

    if deleted:
        try:
            from agent.memory import get_checkpointer
            checkpointer = get_checkpointer()
            if hasattr(checkpointer, "delete_thread"):
                checkpointer.delete_thread(thread_id)
        except Exception as exc:
            print(f"[Agent] Checkpointer cleanup for deleted thread failed ({exc}).", flush=True)

    return deleted
