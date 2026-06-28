# SME-GPT — Demo Recording Script (voiceless)

A shot-by-shot guide for a **silent screen-recording** that shows off every AI
component of SME-GPT. There is no narration, so the story is told through
**on-screen caption cards** and the actions themselves.

Two audiences, one video:
- **On screen (what the viewer reads):** plain business language only — *no
  technical terms* (no "OCR", "LLM", "aggregate_sum", "vector", "tenant").
- **For you / the examiner (the "AI concept" notes below each scene):** these
  name the underlying AI component so you know what each scene is proving. **Do
  not put these on screen** — keep them in your head or in a separate slide deck.

Target length: **3–4 minutes.** Caption cards: ~3 seconds each, big readable font.

---

## Before you record (prep checklist)

- [ ] Backend running (`uvicorn app:app --reload --port 8000`) and **Ollama running** (`ollama serve`).
- [ ] Frontend running (`npm run dev`) at `http://localhost:3000`.
- [ ] Log in once beforehand; start the recording already on the dashboard.
- [ ] **Seed data:** have a few documents already saved (a couple of invoices, a PO, a receipt,
      one with a past due date so the overdue alert fires). Keep the originals handy to re-upload.
- [ ] Have **one clean sample invoice** (PDF or photo) ready to upload live.
- [ ] Have **one Sinhala document** (or a Sinhala query typed out) ready, to prove bilingual support.
- [ ] Set the language to **English** to start; you'll switch to Sinhala near the end.
- [ ] Light mode or dark mode — pick one and stay consistent (dark mode looks great for video).
- [ ] Hide bookmarks/other tabs; full-screen the browser; 1080p or higher.
- [ ] Use a screen recorder that can add text overlays (e.g. ScreenPal, OBS + captions, or add
      caption cards later in CapCut / DaVinci Resolve).

> **Tip:** record each scene as its own clip, then stitch. If a live OCR upload is slow, you can
> trim the wait or speed it up 2× in editing — but *do* show the live result.

---

## Scene 1 — Opening title (5 s)

- **Screen:** black title card.
- **Caption:** "SME-GPT — Smart help for your business documents."
- **Sub-caption:** "Works in English and Sinhala."

> AI concept (not shown): project framing — bilingual document intelligence for Sri Lankan SMEs.

---

## Scene 2 — The dashboard (10 s)

- **Action:** start on the dashboard. Slowly scroll so the stat cards, recent documents, and the
  **notification bell** are visible.
- **Caption:** "Your whole business — invoices, orders, receipts — in one place."
- **Action:** click the **bell**. Show the **overdue payment reminder** notification.
- **Caption:** "It even reminds you when a payment is overdue."

> AI concept: rule-based **overdue detection** (`/overdue-alerts`) deriving aging payables/receivables.

---

## Scene 3 — Upload & automatic reading (35 s) ★ core AI

- **Action:** go to **Upload**. Drag in the sample invoice (or use **Take Photo** on mobile view).
- **Caption:** "Just upload a photo or PDF — no typing."
- **Action:** let the **processing steps animate** (Document Classification → Reading → Checking →
  Finalising). Don't skip this — it's the heart of the demo.
- **Caption:** "It reads the document for you — even messy photos or Sinhala text."
- **Action:** when the **Extracted Preview** appears, slowly highlight the filled-in fields
  (supplier, date, total, line items) and the **confidence badge**.
- **Caption:** "Every field filled in automatically — and it knows it's an invoice, not a receipt."

> AI concept: the full pipeline — **OCR** (Surya) → **semantic OCR post-correction** (C1, numbers
> never altered) → **layout-aware structuring** (C2) → **document-type classification** +
> **structured field extraction** (LLM via Ollama, JSON mode). This single scene proves 4 components.

---

## Scene 4 — You stay in control (10 s)

- **Action:** toggle **Edit**, tweak one field, toggle back. Then click **Confirm and Save**.
- **Caption:** "You can always check and correct before saving."

> AI concept: human-in-the-loop confirmation; arithmetic re-validation on save.

---

## Scene 5 — Proof behind every number (20 s) ★ explainability

- **Action:** open the saved document from the **Repository** → its **Analysis** page.
- **Action:** show the **document image with coloured boxes** over it. Click a box.
- **Caption:** "See exactly where each number came from on the original document."
- **Action:** show the field highlight / source link reacting to the click.
- **Caption:** "Nothing is made up — every figure is traceable."

> AI concept: **provenance / explainable AI** — bbox overlay + field→source mapping (C2 spatial
> chunks, click-to-source). This is a key research differentiator.

---

## Scene 6 — Ask a question in plain language (30 s) ★ core AI

- **Action:** go to **Query**. Type a natural question, e.g. *"How much do I still owe my suppliers?"*
- **Caption:** "Ask anything about your money — in your own words."
- **Action:** (optional) tap the **microphone** and speak the question to show voice input.
- **Caption:** "Type it or just say it."
- **Action:** submit. Land on the **Answer** page; let the answer render.

> AI concept: **neuro-symbolic Question Answering (PAL)** — the model *plans* the query, a symbolic
> validator guards it, and a deterministic engine does the maths (no AI-invented numbers).

---

## Scene 7 — A trustworthy answer (25 s) ★ explainability

- **Action:** on the Answer page, read the headline answer. Point to the **accuracy badge**.
- **Caption:** "A clear answer — with the proof attached."
- **Action:** expand **"How this answer was worked out"** (the step-by-step trace). Scroll the
  four steps: *Where we looked → Documents we used → How we calculated → Your answer.*
- **Caption:** "It shows its working, step by step — like a careful accountant."
- **Action:** expand **Evidence Documents** to show the exact documents behind the total.
- **Caption:** "And the exact documents it used."

> AI concept: **explainable, grounded answering** — the derivation trace + evidence. Note the
> jargon-free wording (we deliberately hide internal terms like operations/field names).

---

## Scene 8 — Cross-document smarts (15 s)

- **Action:** if you have a linked invoice + PO, show the **"Go to PO"** link / **price
  discrepancy** card on the answer or analysis page.
- **Caption:** "It even spots when an invoice doesn't match the original order."

> AI concept: **relationship index (C4)** — entity linking + cross-document discrepancy detection.

---

## Scene 9 — Bilingual (20 s) ★ unique

- **Action:** open the **language switcher**, choose **සිංහල**. Let the UI reload in Sinhala.
- **Caption:** "Prefer Sinhala? One tap."
- **Action:** ask a question **in Sinhala** on the Query page (or show a previously answered
  Sinhala query). Show the answer rendered in Sinhala.
- **Caption:** "It understands and answers in Sinhala too."

> AI concept: **bilingual understanding** — Sinhala/English query normalization + Sinhala-safe OCR
> correction + full Sinhala UI. Rare for local SME software; strong for the AI evaluation.

---

## Scene 10 — Organised automatically (10 s)

- **Action:** go to **Repository**. Show documents already **sorted by type** (Invoice / PO / DN /
  Receipt), use a **status filter** chip and the **date range** filter.
- **Caption:** "Everything sorted and searchable — automatically."

> AI concept: results of automatic **document classification** + workflow status derivation.

---

## Scene 11 — Closing (5 s)

- **Screen:** title card.
- **Caption:** "SME-GPT — your documents, understood."
- **Sub-caption:** "Built for Sri Lankan small businesses."

---

## AI-component coverage checklist

Tick these off when reviewing the final cut — the video should visibly demonstrate each:

- [ ] **OCR + semantic post-correction** (Scene 3) — reads messy/Sinhala documents.
- [ ] **Document-type classification** (Scenes 3, 10) — knows invoice vs receipt vs PO vs DN.
- [ ] **Structured field extraction** (Scene 3) — auto-fills fields + line items.
- [ ] **Layout-aware structuring & provenance** (Scene 5) — boxes + click-to-source.
- [ ] **Neuro-symbolic QA (plan → validate → compute)** (Scenes 6–7) — arithmetic-safe answers.
- [ ] **Explainable derivation trace + evidence** (Scene 7) — shows its working.
- [ ] **Cross-document relationship / discrepancy** (Scene 8).
- [ ] **Bilingual understanding (Sinhala + English)** (Scene 9).
- [ ] **Overdue / insight detection** (Scene 2).

---

## On-screen wording — do / don't

| Don't show (technical) | Show instead (SME-friendly) |
|---|---|
| OCR / extraction / pipeline | "reads the document for you" |
| LLM / model / prompt | "smart assistant" / "it understands" |
| aggregate_sum, sum(payable_amount) | "added up the money you owe" |
| tenant-scoped, database, table | "your own saved documents" |
| vector / embedding / RAG | "finds the right documents" |
| flow_type: payable | "Money you owe" |
| provenance / bounding box | "see where each number came from" |

> The app's answer screen and derivation trace already follow this mapping in code
> (`frontend/src/lib/humanize.ts`), so what's on screen is safe to record as-is.
