# SME-GPT — How to Explain the System (Presentation Guide)

> A layered script: lead with the plain-English "what & why", then reveal the technical "how & why-this-way" for each part. Use the **Say this** lines out loud; keep the **Under the hood** for questions/depth.

---

## 0. The 30-second pitch (open with this)

**Say this:** "SME-GPT lets a small Sri Lankan business owner photograph an invoice or receipt — in Sinhala or English — and instantly turn it into structured financial data they can *ask questions about* in plain language: *'how much do I owe suppliers this month?'* It does the accounting extraction and answers financial questions, so the owner doesn't need an accountant or English fluency."

**Why it matters:** SMEs are the backbone of Sri Lanka's economy but rarely have bookkeeping software that handles **Sinhala**, **messy phone photos**, and **natural-language questions**. That intersection is the gap we fill.

---

## 1. The problem (frame it in 3 sentences)

1. SME owners drown in paper documents and can't afford accounting software or staff.
2. Existing OCR/accounting tools are English-first and expect clean scans, not crumpled bilingual receipts.
3. Even when data is digitized, owners can't *interrogate* it — they want answers ("what's my profit?"), not spreadsheets.

---

## 2. The workflow, in plain language (the demo narrative)

Walk them through exactly what a user does:

1. **Upload / snap a photo** of an invoice, receipt, purchase order, or delivery note.
2. **Watch it process** — a friendly progress spinner (we deliberately hide the technical steps from the user).
3. **Review the extracted fields** — vendor, date, totals, line items — and correct anything (e.g. edit the final total for tax/discount).
4. **Save** — then either *ask a question*, *view the document*, or *upload another*.
5. **Ask in plain language** (Sinhala or English): "How much did I spend last month?" → get a **number, an explanation, and the source documents**.

**Say this:** "Every answer is backed by the actual documents it came from — the system never makes up numbers."

---

## 3. The pipeline (technical, one component at a time)

Present this as a conveyor belt. For each stage: *what it does* → *why we built it this way*.

```
Upload → PDF/Image prep → OCR → LLM correction → Structured extraction
       → Arithmetic validation → Correction engine → Save to Postgres
       → (background) spatial embedding into pgvector
```

### Stage 1 — Document intake & preprocessing
- **What:** PDF pages → images (Poppler); resize to 1600px; make two variants — "printed" and "messy".
- **Why:** Phone photos are skewed, dark, low-contrast. Two variants let us OCR both and *keep the better result* — robustness for real-world inputs.

### Stage 2 — OCR (Surya, bilingual)
- **What:** Runs **Surya OCR** (Sinhala + English) on a GPU, returning text **plus bounding boxes and confidence** per line.
- **Why Surya:** one of the few open OCR engines that handles **Sinhala script** well. It runs remotely on Colab (GPU) with a **local fallback** — if the remote is down, the app still works.
- **Why boxes+confidence:** they enable *provenance* (click a number, see where it came from) and let us trust/distrust specific reads.
- **Honest note:** OCR is the hardest, most error-prone stage — which is exactly why the *next* stage exists.

### Stage 3 — LLM OCR correction (with a numeric safeguard)
- **What:** An LLM fixes OCR typos in common words — but we **mask all numbers and dates before sending**, and restore them after.
- **Why the mask:** an LLM must **never silently change a number** (that would corrupt financial data). So we let it fix "invioce"→"invoice" but physically prevent it from touching "1,540.00". This is a core safety design.

### Stage 4 — Structured extraction
- **What:** An LLM converts the corrected text into a **strict JSON object** (document type, vendor, dates, totals, line items) using JSON-mode output.
- **Why LLM here:** layouts vary wildly; rules-based parsing breaks. An LLM generalizes across formats and languages.

### Stage 5 — Arithmetic validation & correction engine
- **What:** Deterministic (pandas) checks — do line items sum to the total? Derives statuses (paid/overdue, PO approved/fulfilled, etc.).
- **Why:** **We never trust the LLM's math.** Totals are recomputed in code; mismatches are flagged to the user.

### Stage 6 — Persistence
- **What:** Upsert into the `FinancialDocument` table (Postgres), tenant-scoped, with duplicate detection.
- **Why Postgres+pgvector:** one database for both relational data *and* vector search — simpler ops, strong consistency.

### Stage 7 — (Background) spatial embedding
- **What:** After save, spatial "chunks" of the document are embedded (`multilingual-e5-small`, 384-dim, Sinhala-capable) into **pgvector** — done in a background thread so the save feels instant.
- **Why:** enables semantic retrieval (RAG) for future questions without blocking the user.

---

## 4. The star of the show — how questions get answered (the "PAL" engine)

This is your **research contribution** and the most impressive part. Explain it slowly.

**Say this:** "The dangerous, naive way to build this is to hand the question and the numbers to an LLM and let it do the math. LLMs are confidently wrong at arithmetic. We refuse to do that."

**Instead, a 4-step neuro-symbolic pipeline (PAL):**

1. **Scope** — figure out *which documents* the question is about (SQL filter by tenant + company → optional graph expansion → optional vector retrieval).
2. **Plan (LLM)** — the LLM outputs a **strict JSON plan** ("sum the `total` field where `flow_type = payable` in this date range") — *not* an answer, just a plan.
3. **Validate (symbolic guard)** — an allow-list checks the plan: only canonical fields, only known operations. **A bad plan never runs.**
4. **Execute (deterministic)** — the arithmetic is done in **pandas code**, not by the LLM.
5. **Answer (LLM)** — the LLM only *phrases* the already-computed result into a human sentence.

**Why this design (the key insight):** *"The LLM decides **what** to compute; our code decides **how** and actually **does** it. That gives us the flexibility of AI with the correctness of a calculator."* If PAL can't produce a valid plan, it **degrades gracefully** to a rule-based engine — it always answers safely or not at all.

---

## 5. Cross-cutting engineering (mention to show maturity)

- **Bilingual by design:** Sinhala Unicode detection; ~40 Sinhala→English query mappings; LLM prompts include a bilingual glossary; UI fully translated.
- **Tenant isolation everywhere:** every query is scoped to the logged-in user — non-negotiable invariant.
- **Graceful degradation everywhere:** OCR remote→local, PAL→legacy, DB retry on dropped connections, vector/graph features degrade to SQL-only if unavailable.
- **LLM abstraction:** a single router picks **Gemini / DeepSeek / Ollama** per task, with a response cache. Pipeline (extraction) and query (finetuned model) can use different providers — swappable via env vars.
- **Safety invariant:** *the LLM never computes numbers* — enforced by the validator, not by hope.

---

## 6. The tech stack (one slide)

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind 4 | Modern, installable as a mobile PWA |
| Backend | Python 3.12, FastAPI | Async, fast, great for AI workloads |
| Database | PostgreSQL (Supabase) + pgvector | Relational + vector in one store |
| OCR | Surya (GPU, bilingual) | Rare Sinhala support, gives boxes+confidence |
| LLM | Gemini / DeepSeek / Ollama (routed) | Provider-agnostic; cloud speed or local privacy |
| Embeddings | multilingual-e5-small (384-dim) | Local, CPU-friendly, Sinhala-capable |
| Auth | JWT + bcrypt + 2FA + RBAC | Production-grade access control |
| Deploy | Docker + nginx (TLS) + CI | Reproducible, secure transport |

---

## 7. Anticipated hard questions (and crisp answers)

- **"How accurate is the OCR?"** — "OCR alone is imperfect on phone photos; that's why we layer LLM correction with a numeric safeguard, run two image variants and keep the best, and validate arithmetic in code. We also surface confidence and let the user correct before saving."
- **"What if the LLM hallucinates a number?"** — "It structurally can't affect financial figures: numbers are masked during correction, arithmetic is done in pandas, and the plan validator rejects anything outside an allow-list."
- **"Is our financial data safe with a cloud LLM?"** — "Keys are env-gated and we can run fully local via Ollama for sensitive tenants. Cloud is opt-in; roadmap includes on-prem tier + DPAs."
- **"Does it scale?"** — "Stateless FastAPI + pooled Postgres scales horizontally; the only stateful bit (upload session) moves to Redis when we scale out. OCR moves to a hosted GPU."
- **"Why not just use ChatGPT / an existing OCR API?"** — see the comparison report — short answer: **Sinhala + arithmetic correctness + provenance + affordability** for SMEs, which no single existing product covers.
- **"What's not done?"** — Be honest: hosted OCR, at-rest encryption, monitoring/SLA. All operational, all on the roadmap.

---

## 8. Suggested 12-minute talk structure

1. Problem & who it's for — 1.5 min
2. Live demo (upload → correct → save → ask a question) — 4 min
3. The pipeline conveyor belt (Section 3) — 2.5 min
4. The PAL engine — why LLMs don't do our math (Section 4) — 2 min
5. Stack + engineering maturity (5, 6) — 1 min
6. Production readiness — honest status + roadmap (doc 01) — 1 min
7. Q&A

**Closing line:** *"We didn't just wrap an LLM around receipts. We built a system that's correct by construction, works in Sinhala, and is honest about the last mile to production."*
