# Research Contribution — R. Sobatharsan

**Areas:** Component 3 (Neuro-Symbolic Arithmetic Question-Answering — PAL) · UI/UX (bilingual frontend, provenance/evidence presentation, interaction design).

**One-line pitch:** *"I own the reasoning engine and how humans experience it — the neuro-symbolic layer that answers finance questions with guaranteed-correct arithmetic and citations, and the bilingual interface that turns that into something an SME owner can actually trust and use."*

---

## 1. Component 3 — Neuro-Symbolic Arithmetic QA (PAL)

### Problem
People ask *"how much did we earn this month?"* or *"how much do we owe Singer?"*. **LLMs hallucinate arithmetic** — they'll confidently return a wrong sum. In finance, a wrong number is worse than no answer. Yet we still need natural-language understanding to interpret messy, bilingual, typo-ridden questions.

### Approach — *Program-Aided Language models (PAL): the LLM plans, code computes*
This is the system's central research idea. The LLM is **removed from computation entirely**:

```
Query → Scope Resolver → Retriever → Planner(LLM→JSON) → Validator(allow-list)
      → Executor(pandas) → Answer Generator(LLM) → answer + citations + audit
```

1. **Planner (`pal_planner.py`)** — the LLM converts the question into a **strict JSON plan**, never code:
   ```json
   {"task":"aggregate_sum",
    "filters":[{"field":"flow_type","op":"in","value":["receivable","cash_inflow"]},
               {"field":"doc_date","op":"between","value":["2026-07-01","2026-07-31"]}],
    "measure":{"field":"total","agg":"sum"}, "group_by":[], "output":{"format":"currency"}}
   ```
   The prompt is **bilingual** (Sinhala glossary) and is injected with **today's date** so relative periods ("this month") resolve correctly.
2. **Validator (`pal_validator.py`) — the symbolic guard.** Rejects any plan whose task, operator, or field falls outside a **canonical allow-list** (`item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor, flow_type`). A plan **never reaches the executor** unless it passes. On failure, the `error_reason` is fed back to the planner for up to **2 retries**.
3. **Executor (`pal_executor.py`) — deterministic pandas.** Loads canonical rows into a DataFrame and applies filters + aggregation **exactly**. **No `eval`, no `exec`, no LLM math.** Mixed currencies are **not** summed into a meaningless total — it returns `currency:"mixed"` + a per-currency breakdown.
4. **Answer Generator (`pal_answer.py`) — the LLM's *only* other job:** phrase the computed number in Sinhala/English with **row-level provenance** ("You earned LKR 5,000 this month, across 1 receipt"). It phrases; it never decides the number.
5. **Orchestration (`pal_qa.py`)** — wired into `/ask-query`. Includes intent routing that sends income/expense/period questions through PAL (typo-tolerant) and **degrades gracefully to the legacy engine** on any planner failure.

### The research claim
> **Correctness by construction.** By splitting *understanding* (LLM, robust to typos and bilingual phrasing) from *computation* (deterministic pandas, allow-list-guarded), we get natural-language flexibility **and** ~100% arithmetic correctness — without a free-roaming agent that could compute wrong.

### Why *not* an agent (a question you'll get)
An open agent lets the LLM freelance the arithmetic — reintroducing the exact hallucination risk PAL removes. PAL is a **constrained** planner: one validated plan, deterministic execution. That's a *stronger* correctness guarantee than an agent, by design.

### Key files
`pal_planner.py`, `pal_validator.py`, `pal_executor.py`, `pal_answer.py`, `pal_qa.py`, `pal_scope.py`; tests `tests/test_iter5_pal_qa.py`, `tests/test_financial_logic.py`.

### Honest caveats (say them first)
- Citations are document-level today; bbox-level citations need C1/C2 wired into the live ingest.
- Live PAL reads canonical rows from Postgres rather than C2 chunks yet — a contained swap in `pal_scope.py` when chunk retrieval goes live.

---

## 2. UI/UX — the trust layer

### Problem
The target user is a **Sri Lankan SME owner**, not a data analyst. If the interface shows raw IDs, technical jargon, or an un-explained number, they won't trust it. The research value of PAL (correct + explainable) is only *realised* if the UI surfaces the explanation.

### Approach
- **Bilingual by design (`frontend/src/lib/i18n.ts`).** Every UI string exists in English and Sinhala; a language toggle (localStorage + `app-language-changed` event) switches the whole app, and voice input switches between `si-LK` and `en-US`. This is core to reaching non-English-first users.
- **Provenance-first answers.** The answer page renders PAL's **evidence** — each supporting document with its `flow_type`, status badges (PO/invoice/DN), amounts, and dates — so every answer shows *why*. This is the UX manifestation of the "explainable-by-construction" research goal.
- **Human-readable everywhere.** Documents show the **other party's name** with the ID as a small sub-label (not bare `R20`); money is formatted `LKR 1,500.00`; a document upload shows a **plain-language spinner** ("Reading your document…") instead of pipeline jargon.
- **Perceived-performance polish.** **Skeleton loading** on the dashboard and repository (pulsing placeholders instead of "0" or "Loading…"), a **post-save "what next?" flow** (query / view / upload again), and **document thumbnails** before extraction — reducing the anxiety of "did it work?".
- **Editable extraction review.** Users can correct the final total (tax/discount) before saving — keeping a human in the loop over the AI's extraction.

### The research/design claim
> Explainability is a **UX property**, not just a model property. A correct-but-opaque answer isn't trustworthy; the interface must expose the evidence and speak the user's language. The UI is what converts PAL's guarantees into user trust.

### Key files
`frontend/src/lib/i18n.ts`, `frontend/src/app/answer/page.tsx` (evidence/provenance), `frontend/src/app/query`, `dashboard`, `repository`, `upload`, shared UI components (skeletons, badges).

---

## How my parts fit the pipeline

```
(Ashfak: OCR + C1 + RAG + C4)  (Shinthurie: preprocessing + C2 chunks)
                         ↓ clean, scoped, structured data
Query → [My C3: plan → validate → compute → phrase] → answer + evidence
                         ↓
                 [My UI/UX: bilingual, provenance-first presentation]
```
I consume the **scoped, structured data** the others produce, compute the answer **deterministically**, and present it in a way an SME owner **trusts** — closing the loop from scanned paper to a decision.

## Likely questions → answers
- *"How do you guarantee the arithmetic is right?"* → "The LLM only emits a JSON plan; a validator rejects anything off the canonical allow-list; pandas does the actual math. The model literally never computes the number."
- *"What if the question is misspelled or in Singlish?"* → "That's the LLM planner's job — it's robust to typos and mixed language. The correctness guarantee is downstream in the validator + executor, so fuzzy input can't produce a wrong number, only a clarification or a graceful fallback."
- *"Why does the UI matter for a research project?"* → "Because explainability that the user can't see isn't explainability. The evidence panel and bilingual UI are how the correctness guarantee becomes *trust*."

## 30-second viva pitch
"My half is *reasoning and trust*. Component 3 answers finance questions using a neuro-symbolic design: the LLM writes a structured plan, a validator guards it against an allow-list, and deterministic pandas does the arithmetic — so answers are natural-language-flexible but mathematically correct, with citations. Then the UI turns that into something a Sri Lankan SME owner actually trusts — fully bilingual, showing the evidence behind every number, in plain language instead of jargon. Correctness by construction, made usable."
