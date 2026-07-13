# Research Contribution — Ashfak N. A. M.

**Areas:** OCR ingestion engine · Component 1 (Semantic OCR Post-Correction) · Retrieval-Augmented Generation (embeddings + vector search) · Component 4 (Multi-Tenant Relationship Index).

**One-line pitch:** *"I own the parts that find the right documents and turn noisy bilingual scans into clean, machine-usable text — the OCR engine, the AI post-correction that never corrupts a number, the semantic retrieval layer, and the cross-document link graph that lets a PO find its invoice."*

---

## 1. OCR Engine & Version Selection

### Problem
Sri Lankan SME documents are photographed on phones, in **Sinhala and English**, often skewed and low-contrast. A single OCR pass is unreliable, and general OCR engines handle Sinhala poorly.

### Approach
- **Surya OCR** is the engine (strong multilingual + Sinhala coverage). It runs **remotely on Google Colab GPU** (`colab_ocr_client.py`) with a **local Surya fallback**, because CPU inference is too slow for a demo.
- The engine sits behind a **pluggable `OCRService` interface** (`ocr_service.py`, FR-08) so the backend never couples to one OCR implementation. A `boxes_from_surya_v2_page()` adapter normalises Surya v2's block/HTML output into a **canonical box schema** `{text, bbox, confidence, label, page}`, and `MockSuryaOCRService` (fixture-backed) stands in when no GPU backend is available.
- **Version selection (`ocr_selector.py`):** each page is OCR'd in multiple image variants; `select_best_ocr_version()` **scores** each output (penalises leftover HTML tags, rewards Sinhala character coverage and digit density) and picks the best. This is the deterministic "which OCR reading do we trust" gate.

### Key files
`ocr_service.py`, `ocr_selector.py`, `colab_ocr_client.py`, `surya_ocr_colab*.ipynb` (Colab worker), `docs/suryaREADME.md`.

### Explain-it line
*"OCR is an interface, not a hard dependency. We run Surya on a Colab GPU, produce several readings per page, and a deterministic scorer picks the best one — so a bad single pass never silently wins."*

---

## 2. Component 1 — Semantic OCR Post-Correction

### Problem
Raw OCR of Sinhala–English finance text is full of typos (`invioce`→`invoice`), but **an LLM "fixing" text can silently change `500.00` into `5000.0`** — catastrophic for finance.

### Approach — *correctness by construction*
1. **Per-box correction, not whole-page.** Each OCR box is corrected independently (`ocr_correction.py: correct_box/correct_pages`), preserving its bounding box for later provenance.
2. **Numeric safeguard (non-negotiable, deterministic).** A correction is **rejected and the raw OCR text is kept** if the digit count, digit sequence, **or decimal-point position** changes:
   - `_decimal_skeleton` catches the subtle case `extract_digits` misses: `"500.00"→"5000.0"` has the same digit sequence (`50000`) but a different decimal position = a different number.
   - A `.` only counts as a decimal point when between two digits, so `"Rs."` never triggers a false rejection.
3. **Sinhala is preserved, never translated** (Unicode U+0D80–U+0DFF protected via token masking, reused from `llm_correction.py`).
4. **Graceful failure:** LLM down/timeout → use raw OCR text (`source="raw_ocr"`).

### The research claim
> The LLM improves *readability* but is **mathematically forbidden** from altering *value*. Numeric Accuracy Rate (NAR) = 100% by construction; CER (character error) is the quality metric.

### Key files
`ocr_correction.py` (box-level + `safe_correct`), `llm_correction.py` (live whole-text path, SymSpell + masking), tests in `tests/test_iter2_ocr_correction.py`.

### Likely question → answer
- *"How do you know the LLM didn't change a number?"* → "We diff the digit sequence **and** the decimal skeleton before/after. Any mismatch = reject and keep raw OCR. It's impossible for a corrected box to carry a different value."

---

## 3. Retrieval-Augmented Generation (RAG)

### Problem
Users ask questions in natural, messy, bilingual language. We must fetch the **right documents/chunks** to answer — across Sinhala and English — before any computation.

### Approach
- **Embeddings:** `intfloat/multilingual-e5-small` (384-dim, CPU, **supports Sinhala**) via `embedding_service.py`. Chosen for genuine multilingual coverage at a size that runs without a GPU. The model is cached in-process (loaded once).
- **Vector store:** **pgvector** on Supabase Postgres (`ChunkEmbedding`, `vector(384)`), managed in `vector_index.py` (`flatten_chunks_for_embedding`, `embed_rows`, `upsert_chunk_embeddings`).
- **Hybrid scope resolution (`pal_scope.py: resolve_scope_with_rag`):** tenant + company SQL filter → **C4 graph expansion** → optional **pgvector semantic retrieval**. Every stage **degrades silently to SQL-only** if a component is unavailable — retrieval never hard-fails a query.

### The research claim
> Retrieval is **hybrid and tenant-isolated**: symbolic SQL narrows the space, the C4 graph pulls in related docs, and dense multilingual vectors handle vocabulary mismatch — with graceful degradation at every layer.

### Key files
`embedding_service.py`, `vector_index.py`, `pal_scope.py`, tests `tests/test_iter4_vector_index.py`.

### Honest caveat (say it before they ask)
The spatial-chunk vector path is **built and tested but not yet fully wired into the live ingest**; live PAL currently reads canonical rows from Postgres. The retrieval contract is unchanged — swapping in chunk retrieval is contained to `pal_scope.py`.

---

## 4. Component 4 — Multi-Tenant Relationship Index (MT-RI)

### Problem
Related documents don't share vocabulary: a PO says *"laptop"*, the invoice says *"Payment for PO-101"*. A pure vector DB **silos** them, so "Did we pay for PO-101?" fails.

### Approach — *deterministic first, fuzzy second*
- **Postgres is source of truth** (`Entity`, `EntityAlias`, `DocLink`) — tenant-isolated, auditable edges carrying `{page, bbox, chunk_id, rule}` evidence.
- **Normalisation before fuzz:** vendor names lowercased, suffixes stripped (`Pvt Ltd`, `PLC`…); reference numbers regex-canonicalised (`PO-101`→`PO_000101`).
- **Conservative entity resolution:** score ≥ 0.92 → alias; 0.85–0.92 → store alias at lower confidence (**no hard merge**); < 0.85 → new entity. **Never overwrite originals.**
- **Query-time:** `expand_related_docs()` turns a PO into the invoices that reference it, feeding the retrieval scope for C3.

### Key files
`entity_index.py`, schema (`Entity`/`EntityAlias`/`DocLink`), tests `tests/test_iter6_entity_index.py`.

### Why it's mine (connection to RAG)
C4 is the **symbolic half of retrieval** — it expands scope *before* vector search runs, so `pal_scope.py` combines my C4 graph + my RAG layer into one scope resolver.

---

## How my parts fit the pipeline

```
Scan → [OCR engine + selection] → [C1 correct + numeric safeguard] → clean boxes → (C2 spatial → Shinthurie)
Query → [C4 graph expand] + [RAG vector retrieve]  →  scope of docs → (C3 PAL → Sobatharsan)
```
I hand **clean, box-aligned text** to Shinthurie (C2) and a **scoped, relevant document set** to Sobatharsan (C3).

## 30-second viva pitch
"My half is *retrieval and extraction intelligence*. On ingest, Surya OCRs the scan, a scorer picks the best reading, and my Component 1 lets an LLM fix spelling while a numeric safeguard makes it mathematically impossible to alter a value. On query, my Component 4 link-graph pulls in related documents and my multilingual RAG layer retrieves by meaning across Sinhala and English — handing a correct, relevant scope to the reasoning engine. Every layer degrades gracefully instead of failing."
