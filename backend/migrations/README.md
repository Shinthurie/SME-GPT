# Database Migrations

## Convention

Migration files are numbered SQL scripts: `NNN_description.sql` (e.g. `001_add_missing_columns.sql`).

Run them **in order**. Each file is idempotent where possible (uses `IF NOT EXISTS`, `IF column_exists`, etc.).

## Running a migration

```bash
python backend/scripts/run_migration.py backend/migrations/001_add_missing_columns.sql
```

Requires `DATABASE_URL` to be set in `backend/.env`.

## After running a migration

If you added or removed columns from `FinancialDocument`, call `invalidate_column_cache()` from
`dataset_manager.py` or restart the backend so the schema cache is refreshed.

## Migration log

| File | Description | Applied |
|------|-------------|---------|
| `001_add_missing_columns.sql` | Adds `fileSizeKb`, `fieldChunkMapJson`, `safeboxJson`, `spatialChunksJson` | Run manually via Supabase SQL Editor |
