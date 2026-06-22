# SME-GPT — CLAUDE.md

## What This Project Is

Full-stack document processing and financial query system for Small-to-Medium Enterprises (SMEs). Users upload invoices, receipts, purchase orders, and delivery notes (PDFs or images, in English or Sinhala). The app extracts structured financial data via OCR + LLM, stores it in PostgreSQL, and answers natural-language financial queries ("How much do I owe Company X?").

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Next.js 16.2, React 19, TypeScript 5, Tailwind CSS 4 |
| Database | PostgreSQL (via psycopg on backend, Prisma 7 on frontend) |
| LLM | DeepSeek API (OCR correction + structured extraction + answer generation) |
| OCR | Surya OCR — remote via Google Colab (primary), local fallback |
| PDF | pdf2image + Poppler |
| Image processing | OpenCV, Pillow |
| Auth | JWT + bcrypt, optional 2FA, device trust |
| Email | Nodemailer (SMTP) |
| i18n | Custom English/Sinhala translation system |

---

## Directory Layout

```
SME-GPT/
├── backend/
│   ├── app.py                    # FastAPI app, all HTTP endpoints
│   ├── document_pipeline.py      # End-to-end document processing orchestration
│   ├── llm_correction.py         # OCR text correction (DeepSeek + SymSpell)
│   ├── ocr_to_json_extractor.py  # Structured field extraction via DeepSeek
│   ├── ai_helper.py              # Natural-language answer generation
│   ├── data_tools.py             # Financial query analysis & aggregation
│   ├── dataset_manager.py        # PostgreSQL CRUD
│   ├── arithmetic_validator.py   # Validates line-item totals
│   ├── correction_engine.py      # Post-extraction field corrections
│   ├── colab_ocr_client.py       # Remote Colab OCR (primary)
│   ├── local_surya_ocr_client.py # Local Surya OCR (fallback)
│   ├── ocr_selector.py           # Picks best OCR output
│   ├── requirements.txt
│   ├── .env                      # API keys, DB URL, Poppler path
│   ├── saved_documents/          # Processed document JSON storage
│   ├── temp_processing/          # Temp files during pipeline
│   └── dictionaries/             # English + Sinhala spell-check dicts
│
├── frontend/
│   ├── src/app/
│   │   ├── api/                  # Next.js API routes (auth, profile, activity)
│   │   ├── analysis/             # Upload + field preview pages
│   │   ├── dashboard/            # Stats home
│   │   ├── query/                # NL query interface
│   │   ├── repository/           # Document browser
│   │   ├── profile/              # User settings, sessions, 2FA
│   │   └── login/                # Auth pages
│   ├── src/components/           # Reusable React components
│   ├── src/lib/                  # auth.ts, i18n, mail, utils
│   ├── prisma/schema.prisma      # DB schema (User, ActivityLog, etc.)
│   ├── package.json
│   └── .env                      # NEXT_PUBLIC_BACKEND_URL etc.
│
└── surya_ocr_colab.ipynb         # Colab notebook for remote OCR server
```

---

## Backend API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/process-document` | Upload + process document, returns preview |
| POST | `/process-document-stream` | Same, but SSE stream with progress events |
| POST | `/confirm-save` | Persist confirmed extraction to DB |
| PUT | `/documents/{id}` | Update document fields |
| DELETE | `/documents/{id}` | Delete document |
| GET | `/documents` | List user's documents |
| GET | `/documents/{id}` | Get document detail |
| GET | `/dashboard-summary` | Totals: payable, receivable, income, expense |
| POST | `/ask-query` | NL financial query → structured answer |
| GET | `/query-history` | User's saved queries |
| GET/DELETE | `/query-history/{id}` | Single query management |

---

## Document Processing Pipeline (document_pipeline.py)

1. PDF → images (pdf2image + Poppler)
2. Preprocess: resize to 1600px, make two variants — "P" (printed) and "M" (messy)
3. OCR: try Colab remote → fall back to local Surya
4. Select best OCR output (ocr_selector.py)
5. LLM correction (llm_correction.py): fix spelling, preserve Sinhala + numbers
6. Structured extraction (ocr_to_json_extractor.py): DeepSeek → JSON fields
7. Arithmetic validation (arithmetic_validator.py)
8. Field correction (correction_engine.py)
9. Return preview to frontend; user edits → confirm-save → PostgreSQL

---

## Key Environment Variables

### backend/.env
```
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=          # e.g. deepseek-chat
COLAB_OCR_URL=           # ngrok URL of running Colab notebook
POPPLER_PATH=            # e.g. C:\poppler\bin on Windows
DATABASE_URL=            # PostgreSQL connection string
JWT_SECRET=
```

### frontend/.env
```
NEXT_PUBLIC_BACKEND_URL= # http://localhost:8000
DATABASE_URL=            # same PostgreSQL instance
NEXTAUTH_SECRET=
SMTP_HOST= / SMTP_PORT= / SMTP_USER= / SMTP_PASS=
```

---

## Database Schema (Prisma)

- **User** — profile, language pref (en/si), 2FA, session version
- **TrustedDevice** — skip 2FA on known devices
- **LoginVerification** — temporary 2FA tokens
- **ActivityLog** — audit trail
- **UploadedFile** — file metadata
- **query_history** — stored NL query results (shared table with backend)

Backend writes financial documents directly via psycopg (raw SQL / CSV-style table `financial_documents_clean`).

---

## Bilingual (English/Sinhala) Handling

- Sinhala characters detected via Unicode range U+0D80–U+0DFF
- LLM correction skips/preserves Sinhala tokens
- Custom dictionaries for domain terms in both languages
- UI has EN/SI language switcher; translation files in `src/lib/`

---

## Running the Project

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npx prisma generate
npm run dev   # port 3000
```

### Remote OCR
- Open `surya_ocr_colab.ipynb` in Google Colab, run all cells
- Copy the ngrok URL into `backend/.env` as `COLAB_OCR_URL`

---

## Known Architecture Notes

- **Session state**: In-memory dict in `app.py` stores extraction results between `/process-document` and `/confirm-save` steps. Not persistent across restarts.
- **Duplicate detection**: `dataset_manager.py` checks before saving to prevent re-entry.
- **Streaming endpoint**: SSE-based `/process-document-stream` yields progress JSON lines during long processing.
- **Effective flow_type**: Derived — `receivable + received = income`, `payable + paid = expense`.
- **Token masking in correction**: Numbers, dates, IDs are masked before sending to DeepSeek and restored after.
