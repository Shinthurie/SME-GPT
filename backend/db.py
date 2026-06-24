"""PostgreSQL (Supabase) connection helper — pool-backed.

Uses psycopg_pool.ConnectionPool so every request reuses an already-open
connection instead of paying a 200-400 ms TCP+SSL handshake on each call.

Pool settings:
- min_size=1  — keep 1 connection warm at idle
- max_size=8  — Supabase free tier allows ~60 concurrent; 8 is safe
- prepare_threshold=None — required for PgBouncer transaction mode (port 6543)
- reconnect_failed — logs but doesn't crash; the next request will retry

All callers continue to use get_conn() as a context manager:

    with get_conn() as conn:
        cur = conn.cursor()
        ...
"""

import os
import uuid
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Load backend/.env regardless of the process working directory.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to backend/.env "
            "(Supabase pooler URL, port 6543 recommended for PgBouncer)."
        )
    return url


def _make_pool() -> ConnectionPool | None:
    """Build the connection pool at import time; return None if DATABASE_URL
    is absent (e.g. during unit tests that never touch the DB)."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,           # open connections immediately on startup
            reconnect_failed=lambda pool: print(
                "[DB] Connection pool failed to reconnect — will retry on next request.",
                flush=True,
            ),
        )
        print("[DB] Connection pool ready.", flush=True)
        return pool
    except Exception as exc:
        print(f"[DB] Could not create connection pool: {exc}", flush=True)
        return None


_pool: ConnectionPool | None = _make_pool()


@contextmanager
def get_conn():
    """Yield a dict-row connection from the pool (commits on exit, rolls back on error).

    Falls back to a direct psycopg.connect() if the pool isn't available
    (e.g. in unit-test environments where DATABASE_URL is unset or wrong).
    """
    global _pool
    if _pool is not None:
        with _pool.connection() as conn:
            # pool.connection() already handles commit/rollback
            yield conn
    else:
        # Fallback: direct connection (no pool — only in test/CI environments)
        conn = psycopg.connect(
            get_database_url(), row_factory=dict_row, prepare_threshold=None
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def new_id(prefix: str) -> str:
    """Generate a primary-key string (Prisma's cuid() default is client-side,
    so raw inserts must supply their own id)."""
    return f"{prefix}_{uuid.uuid4().hex}"
