# SME-GPT

**Explainable AI for Sinhala & English financial document understanding.**

SME-GPT helps Sri Lankan SMEs upload financial documents (invoices, purchase orders, receipts,
delivery notes — PDFs or images, English or Sinhala), extracts structured financial data with
OCR + LLMs, and answers natural-language financial questions ("How much do I owe Company X?")
with **grounded, provenance-backed, arithmetic-safe** answers.

> Final-year research project. Requirements: [`docs/SRS Document.pdf`](docs/SRS%20Document.pdf) (v1.2)
> and [`docs/Research Components sme gpt.pdf`](docs/Research%20Components%20sme%20gpt.pdf).

---

## Architecture at a glance

A 4-component pipeline (built incrementally — see the roadmap):

1. **C1 — Semantic OCR Post-Correction** — fixes noisy OCR while never altering numbers.
2. **C2 — Layout-Aware Spatial Serialization** — turns boxes into header-bound, provenance-rich chunks.
3. **C3 — Neuro-Symbolic PAL QA** — LLM plans, a deterministic executor computes (no math hallucinations).
4. **C4 — Multi-Tenant Relationship Index** — links documents/vendors/refs for cross-document answers.

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

Python 3.12 · FastAPI · Next.js 16 / React 19 / TypeScript / Tailwind 4 · **Supabase Postgres +
pgvector** (Prisma 7 on the frontend, psycopg on the backend) · **Cloud LLM** (DeepSeek by default,
Gemini 2.5 Flash when a key is set, routed via `llm_client.py`) · **Surya OCR** (remote via Colab,
local fallback) · `multilingual-e5-small` embeddings · **Supabase Storage** for document images ·
JWT + bcrypt auth with optional 2FA · Docker.

---

## Documentation

| Doc | What |
|---|---|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Iteration plan (0–8) with checkboxes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Target architecture, data flow, artifact contracts |
| [docs/WORK_DIVISION.md](docs/WORK_DIVISION.md) | Who owns what (flexible) |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Branching, commits, PRs, local setup |
| [docs/TESTING.md](docs/TESTING.md) | Test strategy + research metrics |
| [docs/gap-analysis.md](docs/gap-analysis.md) | SRS FR/NFR traceability |
| [docs/phase3-retirement-plan.md](docs/phase3-retirement-plan.md) | Legacy query engine → agentic engine migration plan |
| [docs/components/](docs/components/) | Per-component specs (C1–C4) |
| [API_CONTRACT.md](API_CONTRACT.md) | Backend ↔ frontend contract |

---

## Quick start

### LLM provider (required before the backend)
Local Ollama inference has been removed (CPU Llama 3 was too slow and weak at Sinhala).
Set at least one cloud key in `backend/.env`: `DEEPSEEK_API_KEY` (default) or
`GEMINI_API_KEY` (preferred when set). This means document text and queries are sent to a
third-party LLM — see the privacy note in [docs/SECURITY.md](docs/SECURITY.md).

### Backend
```bash
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env        # fill in your keys (DATABASE_URL, JWT_SECRET, DEEPSEEK_API_KEY / GEMINI_API_KEY, SUPABASE_*)
uvicorn app:app --reload --port 8000
```

> **Document images** are uploaded to a Supabase Storage bucket (default name `documents`) and
> served via short-lived signed URLs, so they display on any machine sharing the database. Set
> `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` in `backend/.env`.
> If unset, images fall back to the backend's local `saved_documents/` folder (single-machine only).

### Frontend
```bash
cd frontend
npm install
cp .env.example .env        # fill in values
npx prisma generate
npm run dev                  # http://localhost:3000
```

### Remote OCR (optional)
Open `surya_ocr_colab.ipynb` in Google Colab, run all cells, copy the ngrok URL into
`backend/.env` as `COLAB_OCR_URL`. If unset, the local Surya fallback is used.

---

## Status

Working full-stack application on Supabase Postgres. The 4-component pipeline (C1–C4), the
two-tier NL query engine (PAL + legacy), RBAC, audit logging, 2FA, GDPR export/delete, PWA, and
the PO/DN/invoice workflow are all live. See [docs/ROADMAP.md](docs/ROADMAP.md) for the remaining
roadmap (charts, supplier directory, cross-document comparison UI).

## Recent changes

Most recent first. See the git history / merged PRs for full detail.

- **Document images via Supabase Storage** — images now upload to the `documents` bucket on save
  and render anywhere through signed URLs (previously local-disk only, so they never showed on a
  second machine). New `backend/storage_client.py`; graceful local fallback.
- **Overdue payment alerts (IT-23)** — `GET /overdue-alerts` flags past-due / aging payables,
  receivables and invoices; the dashboard surfaces them as notifications (deduped per document).
- **PO approval workflow (IT-27)** — one-click Approve / Reject on the analysis page writing the
  real `po_status` + `approved_by` (bilingual).
- **Repository upload-date filter (IT-21)** — `GET /documents?from=&to=` with a date picker.
- **Ollama JSON output mode (IT-28)** — extraction uses `format="json"` to cut JSON parse failures.
- **Full Sinhala coverage + refined dark mode** — every page now honours the EN/SI toggle
  (`frontend/src/lib/i18n.ts`, parity-checked); neutral dark-mode palette replacing the old one.

## Team

- **Ashfak** — Backend + AI/ML
- **Shinthurie** — Frontend + DB + UX

(Ownership is flexible — see [docs/WORK_DIVISION.md](docs/WORK_DIVISION.md).)
