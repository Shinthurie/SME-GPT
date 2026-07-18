# Deploying SME-GPT

Two supported setups:

- **[A. Frontend on Vercel, backend on your laptop via a tunnel](#a-vercel--laptop-backend-tunnel)** — free, what to use before you have a server.
- **[B. Frontend on Vercel, backend on a VPS / container host](#b-vercel--a-real-backend-host)** — the permanent setup.

Both reuse the existing **Supabase** Postgres, and both need the **Colab OCR
notebook** running for document uploads.

---

## A. Vercel + laptop backend (tunnel)

```
Phone/browser → Vercel (frontend, HTTPS)
                   ↓
            Cloudflare tunnel (public HTTPS)
                   ↓
            Your laptop: FastAPI :8000
                   ↓                 ↓
          Supabase (cloud)    Colab OCR (ngrok)
```

The tunnel is required for two reasons: your phone can't reach `localhost`, and
a browser will not let an HTTPS page (Vercel) call a plain-HTTP backend.

### One-time: deploy the frontend

1. Vercel → **Add New → Project** → import the repo, **Root Directory `frontend`**.
2. Environment variables:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_BACKEND_URL` | anything for now — it's only the *default* (see below) |
   | `DATABASE_URL` | Supabase string (Prisma needs it at build time) |
   | `NEXTAUTH_SECRET` | random string |
   | `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | email settings |

### Each session

1. **Backend** — in `backend/.env` set `JWT_SECRET`, `DATABASE_URL`, an LLM key
   (`DEEPSEEK_API_KEY` or `GEMINI_API_KEY`), and:
   ```
   CORS_ALLOW_ORIGINS=https://<your-app>.vercel.app
   ```
   Then run it:
   ```bash
   cd backend
   uvicorn app:app --port 8000
   ```

2. **Tunnel** — in a second terminal:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   It prints something like `https://random-words-1234.trycloudflare.com`.

3. **Point the app at the tunnel** — open the deployed site → **Settings →
   Preferences → Backend connection**, paste the tunnel URL, **Save & reload**.

   This is stored in `localStorage`, so it overrides the build-time
   `NEXT_PUBLIC_BACKEND_URL` **without a redeploy** — which matters because
   quick-tunnel URLs change every restart. Set it once per session, on each
   device you're testing from. "Use default" clears it.

4. **OCR** — run `surya_ocr_colab.ipynb` in Colab, copy its ngrok URL into
   `COLAB_OCR_URL` in `backend/.env`, restart the backend.

Everything except **document upload** works without the Colab notebook running.

### Limits of this setup

- Your laptop must be awake and online; uploads travel over your home *upload*
  bandwidth.
- Quick-tunnel URLs rotate on restart (hence the Settings override). A **named**
  Cloudflare tunnel with your own domain gives a permanent URL if you want one.

---

## B. Vercel + a real backend host

When you have a VPS (or any container host), `backend/Dockerfile` runs as-is.
It listens on `${PORT:-7860}`, so it works both where a port is injected
(Cloud Run, Render) and where it isn't.

```bash
# on the server
git clone <repo> && cd SME-GPT/backend
docker build -t sme-gpt-backend .
docker run -d --restart unless-stopped -p 8000:8000 \
  -e PORT=8000 \
  -e JWT_SECRET=... \
  -e DATABASE_URL=... \
  -e DEEPSEEK_API_KEY=... \
  -e CORS_ALLOW_ORIGINS=https://<your-app>.vercel.app \
  -e COLAB_OCR_URL=... \
  --name sme-gpt sme-gpt-backend
```

Build it **on the server** — it downloads PyTorch (~800 MB) and bakes in the
embedding model, which is painful over a slow home connection.

Then put HTTPS in front (your frontend is HTTPS, so the backend must be too).
Easiest is **Caddy**, which gets a Let's Encrypt certificate automatically:

```
api.yourdomain.com {
    reverse_proxy localhost:8000
}
```

Finally set `NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com` in Vercel and
redeploy. With a permanent URL the Settings override stays empty.

> **Host notes.** Hugging Face Spaces used to be a good free option but Docker
> hosting there is now paid. Google Cloud Run works on the free tier (scales to
> zero; cold starts reload the model). Render's free tier is 512 MB — too small
> for the embedding model. Oracle Cloud's Always Free ARM VM is generous but
> its free capacity is frequently unavailable.

---

## Known limitations (both setups)

- **Ephemeral image storage.** Saved document *images* live on the backend's
  local disk. On a container host with an ephemeral filesystem they're cleared
  on restart — document *data* is safe in Postgres, only image previews and
  bbox overlays for older docs stop loading. Moving image storage to Supabase
  Storage / S3 is future work.
- **Single instance only.** The backend holds extraction state in memory
  between `/process-document` and `/confirm-save`, so don't run more than one
  instance or autoscale it.
- **OCR is manual.** Uploads need the Colab notebook running and
  `COLAB_OCR_URL` pointed at its current ngrok URL.
