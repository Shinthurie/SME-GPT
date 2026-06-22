"""PostgreSQL (Supabase) connection helper for the backend.

Iteration 1 replaces the CSV store with the Postgres schema managed by Prisma
(see docs/design/iter-1-schema.md). The backend reads/writes those tables with
psycopg (raw SQL); Prisma remains the single migration source of truth.

Table/column identifiers are Prisma defaults (PascalCase tables, camelCase
columns) and must be double-quoted in SQL.
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
            "(Supabase direct connection, port 5432)."
        )
    return url


@contextmanager
def get_conn():
    """Yield a committed connection (rolls back on error). Rows as dicts."""
    conn = psycopg.connect(get_database_url(), row_factory=dict_row)
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
