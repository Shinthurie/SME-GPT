# Research Contribution — Shinthurie M.

**Areas:** OCR image preprocessing (the vision pipeline before OCR) · Component 2 (Layout-Aware Spatial Serialization).

**One-line pitch:** *"I own the transformation from raw pixels to structured layout — first cleaning and standardising the scanned image so OCR can read it, then reconstructing the document's spatial layout (rows, headers, values) into deterministic, provenance-carrying chunks that make retrieval and reasoning precise."*

---

## 1. OCR Image Preprocessing (the vision pipeline)

### Problem
Input is whatever the SME owner photographed: phone snaps, skewed pages, mixed lighting, PDFs and images, printed *and* faint/"messy" documents. Feeding that raw into OCR gives poor, inconsistent text. **OCR quality is capped by image quality**, so this stage sets the ceiling for everything downstream.

### Approach
Implemented in `document_pipeline.py` (`standardize_to_images`, `preprocess_images`):
1. **Format standardisation** — PDFs are rasterised to images at **300 DPI** via `pdf2image` + Poppler; images pass straight through. One uniform code path regardless of input type.
2. **Resize to a consistent working resolution (~1600px)** — normalises scale so downstream clustering thresholds behave predictably across documents.
3. **Two preprocessing variants per page — the key idea:**
   - **"P" (printed)** — binarised / high-contrast, tuned for clean printed text.
   - **"M" (messy)** — bilateral-filtered / deskew-friendly, tuned for faint, noisy, or handwritten-ish documents.
   Producing **both** variants and letting the OCR-selection stage pick the best reading per page means we don't have to guess the document's quality up front.
4. **Deskew** correction so rotated scans don't break row alignment (which my Component 2 depends on).

### The research claim
> Instead of one "average" preprocessing that's mediocre for everything, we generate **multiple targeted renderings** (printed vs. messy) and let a downstream scorer choose — robustness through diversity, not a single fragile heuristic.

### Key files
`document_pipeline.py` (`standardize_to_images`, `preprocess_images`), Poppler/`POPPLER_PATH` config.

### Connection to the team
My preprocessed variants feed **Ashfak's OCR engine**; his `ocr_selector.py` scores the readings my P/M variants produced. My **deskew + consistent scale** is a precondition for my *own* Component 2 row clustering to work.

### Explain-it line
*"I turn any photo or PDF into two clean, standardised renderings — one tuned for crisp print, one for messy scans — so OCR always has a good image to read and my layout stage always has straight, consistently-scaled rows to cluster."*

---

## 2. Component 2 — Layout-Aware Spatial Serialization

### Problem
OCR gives a **bag of `text + bbox` tokens**. It loses the *table structure* — that `500.00` belongs to the **Total** column of the **Apple** row. Flatten that to plain text and a retriever/LLM can no longer tell which number is a quantity, a unit price, or a total. Finance answers live in that structure.

### Approach — *deterministic, template-based, no LLM paraphrasing*
Implemented in `spatial_serialization.py` (`build_spatial_chunks` is the entry point):

1. **Row clustering (y-axis).** Group tokens by vertical alignment. Uses `y_center` and a **dynamic threshold** from the median text height (`median(text_height) * alpha`, `alpha ≈ 0.6–1.2`) so it adapts to font size rather than a hardcoded pixel gap.
2. **Header detection.** Match rows against bilingual header keywords — English (`description, qty, unit price, total, tax, VAT`) and **Sinhala** (`විස්තරය, ප්‍රමාණය, ඒකක මිල, මුළු, බදු, වැට්`). Matching uses **word boundaries**, not bare substring (so `"no."` doesn't false-match inside `"now"`).
3. **Header→row binding (x-axis).** Assign each data token to the nearest header by x-centre; ambiguous tokens → `unknown_column` (never dropped).
4. **Template serialization (deterministic).** Emit structured chunks, e.g.
   `LineItem | Description: Apple | Qty: 5 | UnitPrice: 100.00 | Total: 500.00`.
5. **Chunking strategy:** ≤ 30 rows → one chunk per row; larger tables → blocks of 5–10 rows **with the header repeated** inside each block so every chunk is self-describing.

Each **SpatialChunk** carries **provenance** (`page`, `bbox`, per-token bboxes) and `quality` scores (`struct_confidence`, `header_bound`, `row_cluster_confidence`) — enabling **click-to-source UI highlighting** and traceable answers.

### Two research-worthy design decisions
- **Deterministic over generative.** Serialization is templates, not an LLM — so the structure of a value **cannot be hallucinated**. This is the layout-layer analogue of the C1/C3 "keep the LLM away from the facts" principle.
- **"Never drop tokens."** Every failure mode (no header, skew, sparse columns) has a fallback that still emits best-effort chunks *with provenance*, rather than losing data.
- **Table-cell expansion:** Surya v2 returns one bbox per *table*, not per cell. `ocr_service.table_block_to_cell_boxes` expands a table block into per-cell boxes over a uniform grid so my clustering has real per-cell geometry (a documented approximation — Surya doesn't expose true cell coordinates).

### Key files
`spatial_serialization.py` (`cluster_rows`, `detect_header_row`, `bind_row_to_headers`, `serialize_*`, `build_spatial_chunks`), `spatial_serializer.py`, table-cell expansion in `ocr_service.py`, tests `tests/test_iter9_pipeline_wiring.py`.

### Honest caveats (say them first)
- Row clustering currently runs once per page, not per-table; two tables sharing a y-range would need per-table clustering first (tracked in ROADMAP).
- C2 is a **standalone, tested module** not yet fully wired into the live `/process-document` path — it's ready to consume C1's boxes the moment the live pipeline switches from whole-text extraction.

---

## How my parts fit the pipeline

```
Raw scan/PDF → [My preprocessing: standardise + P/M variants + deskew] → OCR (Ashfak)
OCR boxes → C1 correct (Ashfak) → [My C2: cluster rows → bind headers → template chunks + provenance] → retrieval/reasoning
```
I sit at **both ends of the vision layer**: I prepare the image *before* OCR, and I reconstruct the layout *after* OCR. My output chunks are what make Ashfak's retrieval precise and Sobatharsan's answers citable.

## Likely questions → answers
- *"Why two preprocessing variants instead of one good filter?"* → "Document quality varies wildly; one filter is a compromise. Two targeted renderings + a downstream scorer beats guessing the document type up front."
- *"Why templates instead of asking an LLM to structure the table?"* → "So structure can't be hallucinated. The mapping from tokens to `Qty/UnitPrice/Total` is deterministic and auditable — with a bbox for every field."
- *"How do you handle Sinhala tables?"* → "Header keywords and clustering are language-agnostic on geometry; the header list is bilingual, and unmapped headers keep their original Sinhala text as the field key instead of being dropped."

## 30-second viva pitch
"My half is the *vision-to-structure* pipeline. Before OCR, I standardise every scan or PDF and produce two targeted renderings — one for crisp print, one for messy documents — so OCR always gets a clean, deskewed image. After OCR, my Component 2 reconstructs the lost table layout: it clusters tokens into rows, binds each value to its bilingual header, and serialises deterministic, provenance-carrying chunks — so a `500.00` is known to be the *Total* of the *Apple* row, with a bounding box to prove it. No LLM ever invents that structure."
