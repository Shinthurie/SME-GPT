# SME-GPT Security Notes

## Encryption at Rest (FR-31)

### What IS encrypted

- **Database content** — All document data stored in PostgreSQL (Supabase) is protected by AES-256 encryption at the infrastructure level (AWS RDS transparent encryption). This covers all rows in `FinancialDocument`, `LineItem`, `query_history`, `ActivityLog`, and all Prisma-managed tables.

### What is NOT application-layer encrypted

- **`backend/saved_documents/` image files** — Processed document images (`.png`, `.jpg`) are written to the local filesystem at `backend/saved_documents/`. These files are NOT encrypted at the application layer.

  **Production recommendation:** Place this directory on an encrypted volume:
  - AWS: use EBS volumes with encryption enabled (AES-256 via AWS KMS)
  - Linux: LUKS volume encryption
  - The path is configured via `SAVED_DOCS_DIR` in `backend/app.py`

- **`backend/temp_processing/`** — Temporary files created during OCR processing. These are short-lived and deleted after each pipeline run, but should also reside on an encrypted volume in production.

## Third-Party LLM Processing / Data Residency

**Acknowledged trade-off (recorded here and in code; deliberately not surfaced in the UI).**

Earlier versions supported a *local* LLM (Ollama / Llama 3) so that OCR'd document text and
user queries could be processed entirely on-premise, keeping financial data inside the deployment
boundary. Local inference was removed because CPU-only Llama 3 was too slow and produced poor
Sinhala output, which is unacceptable for user-facing answers.

**Consequence:** OCR'd financial-document text and every natural-language query are now transmitted
to a third-party cloud LLM API — **DeepSeek** by default, or **Gemini** when a key is configured.
Financial data therefore leaves the machine. This is an accepted trade-off (speed + Sinhala quality
prioritised over on-prem data residency) for this deployment.

- Documented in code at the top of [`backend/llm_client.py`](../backend/llm_client.py)
  (the `PRIVACY TRADE-OFF` note) and via `LLMUnavailableError` semantics.
- **Mitigations:** numbers/dates and Sinhala tokens are masked before OCR-correction calls
  (`llm_correction.py`); prompts carry only the minimum text needed; provider API keys are never
  logged. Choose a provider whose data-retention terms match your compliance needs.
- **Not shown in the UI** per an explicit product decision. The research paper's discussion of
  local/on-prem inference is intentionally left unchanged (local inference remains *possible* but
  compute-heavy; the API path is used for the product build).

## Authentication

- JWT tokens signed with HS256; secret must be set via `JWT_SECRET` env var (app refuses to start with the default or empty secret).
- Passwords hashed with bcrypt via Next.js Auth.
- Optional 2FA (TOTP) and device trust.
- Session version invalidation on password reset.

## Transport Security

- All frontend↔backend traffic should be served over TLS (HTTPS). In development, HTTP localhost is used. In production, use a reverse proxy (nginx, Caddy, Render, Vercel) that terminates TLS.

## RBAC

- Roles: `owner`, `accountant`, `admin`, `auditor`
- Write operations require `owner` or `accountant` role
- Admin-only operations (audit log pruning) enforce `admin` role via `require_admin_role()`
- All sensitive operations are audit-logged to `ActivityLog`

## Data Isolation

- All document queries are scoped by `tenantId` (user ID). One user cannot access another user's documents.
- Rate limiting prevents abuse of LLM-calling endpoints (`/ask-query`: 30 req/60s, `/process-document*`: 10 req/60s).
