"""PostgreSQL (Supabase) connection helper — pool-backed.

Uses psycopg_pool.ConnectionPool so every request reuses an already-open
connection instead of paying a 200-400 ms TCP+SSL handshake on each call.

Pool settings (both pools use dict_row so callers get named columns):
  min_size=1  — keep 1 connection warm at idle
  max_size=8  — stays within Supabase free tier limit (~60 concurrent)
  prepare_threshold=None — required for PgBouncer transaction mode (port 6543)

All callers continue to use get_conn() as a context manager:

    with get_conn() as conn:
        cur = conn.cursor()
        ...  # rows are dicts: row["columnName"]
"""

import os
import uuid
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load backend/.env regardless of the process working directory.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to backend/.env "
            "(use Supabase pooler URL port 6543 for best performance)."
        )
    return url


# ---------------------------------------------------------------------------
# Connection pool — created once at import time, reused for every request.
# Falls back to None if DATABASE_URL is absent (unit-test environments).
# ---------------------------------------------------------------------------
_pool = None

def _init_pool():
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        return
    try:
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
            reconnect_failed=lambda p: print(
                "[DB] Pool reconnect failed — will retry on next request.", flush=True
            ),
        )
        print("[DB] Connection pool ready (min=1, max=8).", flush=True)
    except ImportError:
        # psycopg_pool not installed — fall back to per-request connections
        print("[DB] psycopg_pool not available, using per-request connections.", flush=True)
    except Exception as exc:
        print(f"[DB] Pool init failed ({exc}), using per-request connections.", flush=True)

_init_pool()


@contextmanager
def get_conn():
    """Yield a dict-row connection (commits on success, rolls back on error).

    Uses the connection pool when available; falls back to a direct
    psycopg.connect() in environments where the pool is unavailable.
    """
    if _pool is not None:
        with _pool.connection() as conn:
            yield conn
    else:
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
