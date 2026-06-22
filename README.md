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
pgvector** · **DeepSeek API** · **Surya OCR** (standalone, pluggable) · Docker.

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
| [docs/components/](docs/components/) | Per-component specs (C1–C4) |
| [API_CONTRACT.md](API_CONTRACT.md) | Backend ↔ frontend contract |

---

## Quick start

### Backend
```bash
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env        # fill in your keys
uvicorn app:app --reload --port 8000
```

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

Migrating from a prototype (CSV-backed) to the professional 4-component system above.
See [docs/ROADMAP.md](docs/ROADMAP.md) for current progress.

## Team

- **Ashfak** — Backend + AI/ML
- **Shinthurie** — Frontend + DB + UX

(Ownership is flexible — see [docs/WORK_DIVISION.md](docs/WORK_DIVISION.md).)
