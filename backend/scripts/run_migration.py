"""
Migration runner — applies a numbered SQL file to the configured DATABASE_URL.

Usage:
    python backend/scripts/run_migration.py backend/migrations/001_add_missing_columns.sql
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory (one level up from scripts/)
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set in backend/.env", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python run_migration.py <path/to/migration.sql>", file=sys.stderr)
    sys.exit(1)

migration_file = Path(sys.argv[1])
if not migration_file.exists():
    print(f"ERROR: Migration file not found: {migration_file}", file=sys.stderr)
    sys.exit(1)

sql = migration_file.read_text(encoding="utf-8")

try:
    import psycopg
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"OK — migration applied: {migration_file.name}")
except Exception as e:
    print(f"ERROR — migration failed: {e}", file=sys.stderr)
    sys.exit(1)
