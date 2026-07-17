# Deploying SME-GPT

This guide hosts the **backend on Hugging Face Spaces** (free CPU tier — it has
enough RAM for the embedding model), the **frontend on Vercel**, and reuses your
existing **Supabase** Postgres. OCR stays on Colab, started manually when you
upload.

```
Vercel (Next.js)  ──HTTPS──►  HF Space (FastAPI)  ──►  Supabase (Postgres + pgvector)
                                     │
                                     └──►  Colab Surya OCR (ngrok, started on demand)
```

---

## 1. Backend → Hugging Face Space

### 1.1 Create the Space
1. https://huggingface.co → **New → Space**.
2. **SDK: Docker**, blank template. Name it e.g. `sme-gpt-backend`.
3. Leave it **private** if you don't want the code public (still gets a public API URL).

### 1.2 Push the `backend/` folder to it
The Space is its own git repo. Push just the `backend/` subtree into it from
your local clone:

```bash
# one-time: add the Space as a remote (use your HF username/space name)
git remote add hf-space https://huggingface.co/spaces/<user>/sme-gpt-backend

# push the backend/ subdirectory to the Space's root
git subtree push --prefix backend hf-space main
```

`backend/Dockerfile` and `backend/README.md` (with the Spaces frontmatter)
become the Space root, so it builds automatically. The first build takes
~10–15 min (it installs PyTorch and bakes in the embedding model).

> Re-deploying later: commit your changes to the SME-GPT repo, then run the
> `git subtree push` line again.

*(Alternative if `subtree push` is awkward: clone the Space repo separately and
copy the contents of `backend/` into it, then `git push`.)*

### 1.3 Set the secrets
In the Space: **Settings → Variables and secrets → New secret**, add:

| Name | Value |
|---|---|
| `JWT_SECRET` | any long random string (same one your users' tokens were signed with, if you have existing accounts) |
| `DATABASE_URL` | your Supabase pooler string (port **6543**) |
| `DEEPSEEK_API_KEY` **or** `GEMINI_API_KEY` | your LLM key |
| `CORS_ALLOW_ORIGINS` | your Vercel URL, e.g. `https://sme-gpt.vercel.app` (add more comma-separated) |
| `COLAB_OCR_URL` | the ngrok URL from your running Colab notebook (update it each session) |

After saving secrets the Space restarts. When it's healthy, note the API URL:
`https://<user>-sme-gpt-backend.hf.space`.

Quick check: open `https://<user>-sme-gpt-backend.hf.space/docs` — the FastAPI
Swagger page should load.

---

## 2. Frontend → Vercel

1. https://vercel.com → **Add New → Project** → import the GitHub repo.
2. **Root Directory:** `frontend`.
3. **Environment Variables:**

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_BACKEND_URL` | `https://<user>-sme-gpt-backend.hf.space` (no trailing slash) |
   | `DATABASE_URL` | same Supabase string (Prisma needs it at build time) |
   | `NEXTAUTH_SECRET` | a random string |
   | `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | your email settings (for 2FA / reset mail) |

4. Deploy. Vercel runs `npm run build` (which runs `prisma generate`).

Once live, copy the Vercel URL back into the Space's `CORS_ALLOW_ORIGINS` secret
if you hadn't already, so the browser is allowed to call the API.

---

## 3. Colab OCR (manual, on demand)

Uploads need OCR, which runs in `surya_ocr_colab.ipynb`:

1. Open it in Google Colab, **Run all**.
2. Copy the ngrok URL it prints.
3. Update `COLAB_OCR_URL` in the Space secrets (the Space restarts).

While that notebook isn't running, everything except **document upload** still
works (query, repository, dashboard, chat).

---

## Known limitations on the free tier

- **HF Spaces sleeps** after ~48 h idle and cold-starts on the next request
  (~1–2 min to wake). Fine for on-demand use.
- **Ephemeral filesystem:** saved document *images* (`saved_documents/`) are
  cleared on restart/rebuild. Document *data* is safe in Postgres — only the
  image previews / bbox overlays for older docs stop loading. To make them
  durable, move image storage to Supabase Storage or S3 (future work).
- **In-memory upload sessions:** the backend holds extraction state between
  `/process-document` and `/confirm-save` in memory, so run a **single** backend
  instance (don't autoscale the Space).
- **Long uploads:** if the extraction stream ever hits a proxy timeout on
  Spaces, a small always-on VM (Oracle Cloud Always Free) or Cloud Run is the
  next step up.

## Other backend hosts

The same `Dockerfile` runs unchanged on **Google Cloud Run** (scales to zero,
generous free tier, cold-start reloads the model) and **Render** (needs a paid
instance — the free 512 MB is too small for the embedding model). For a truly
always-on free box, an **Oracle Cloud Always Free** ARM VM has plenty of RAM but
you manage it yourself.
