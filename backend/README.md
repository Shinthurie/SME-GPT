---
title: SME-GPT Backend
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# SME-GPT Backend

FastAPI service for the SME-GPT document-processing and financial-query system.
This folder is deployable as a **Hugging Face Space (Docker SDK)** — the YAML
frontmatter above is what tells Spaces to build from the `Dockerfile`.

See [`docs/DEPLOY.md`](../docs/DEPLOY.md) in the repo for full hosting steps.

## Required environment variables / secrets

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | **Required.** App refuses to start without it. |
| `DATABASE_URL` | **Required.** Postgres/Supabase connection string (pooler port 6543). |
| `DEEPSEEK_API_KEY` *or* `GEMINI_API_KEY` | **Required.** At least one LLM provider (Gemini preferred when set). |
| `CORS_ALLOW_ORIGINS` | Comma-separated list — set to your Vercel frontend URL. |
| `COLAB_OCR_URL` | ngrok URL of the running Surya OCR Colab notebook (needed only while uploading). |

## Notes

- The container listens on `${PORT:-7860}` — 7860 on Spaces, or the host's
  injected `$PORT` on Cloud Run / Render.
- Saved document images are written to a local `saved_documents/` dir, which is
  **ephemeral** on Spaces (cleared on restart). Database records persist in
  Postgres; only the cached image files are lost on a rebuild.
