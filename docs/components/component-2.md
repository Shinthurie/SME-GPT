# Component 2 — Layout-Aware Spatial Serialization

> Adapted from `docs/Research Components sme gpt.pdf` (Research Component 2).

## Purpose

Convert spatially-grounded OCR tokens (`text + bbox`) into **layout-preserving, template-based
semantic chunks** that bind values to their headers, preserve row relationships, and keep provenance
for UI highlighting. Runs **after C1, before vector indexing and C3**.

## Design goals

- Preserve spatial semantics (row / label / value)
- Improve retrieval precision for price/qty/total queries
- **Deterministic** — template-based serialization, no LLM paraphrasing
- Provenance: every chunk traces to page + bbox
- Multilingual (Sinhala/English headers and values)

## Inputs

- `tenant_id`, `document_id`, optional `page_images[]`
- `final_safe_boxes.json` (from C1) — **mandatory**

## Output — `spatial_chunks.json`

Top-level:
```json
{ "tenant_id": "...", "document_id": "...", "version": "1.0",
  "language_hint": ["si","en"], "pages": [ { "page": 1, "chunks": [ /* SpatialChunk */ ] } ] }
```

SpatialChunk (required: `chunk_id, chunk_type, text, provenance.page, provenance.bbox,
metadata.source_component`):
```json
{ "chunk_id": "ch_000012", "chunk_type": "line_item_row",
  "table_id": "t1", "row_id": "row_007", "header_id": "hdr_01",
  "text": "LineItem | Description: Apple | Qty: 5 | UnitPrice: 100.00 | Total: 500.00",
  "fields": { "Description": {"value":"Apple","token_ids":["tok_31"]},
              "Qty": {"value":"5","token_ids":["tok_32"],"locked_digits":true},
              "UnitPrice": {"value":"100.00","token_ids":["tok_33"],"locked_digits":true},
              "Total": {"value":"500.00","token_ids":["tok_34"],"locked_digits":true} },
  "provenance": { "page":1, "bbox":[110,290,610,345], "token_bboxes": { "tok_31":[120,300,200,335] } },
  "quality": { "struct_confidence":0.86, "header_bound":true, "row_cluster_confidence":0.90 },
  "metadata": { "currency":"LKR", "doc_type":"invoice", "source_component":"component_2",
                "created_at":"..." } }
```
`chunk_type ∈ {line_item_row, line_item_block, key_value, header, section_text}`.

## Algorithm

1. **(Optional) ROI detection** — OpenCV line/contour grouping for table-ish zones. Skip if row
   clustering is reliable.
2. **Row clustering (y-axis)** — group tokens by vertical alignment.
   `y_center=(y1+y2)/2`, `text_height=(y2-y1)`, `dynamic_y_threshold = median(text_height)*alpha`,
   `alpha ≈ 0.6–1.2` (tune on samples).
3. **Header detection** — rows matching known keywords:
   - English: description, qty, quantity, unit price, total, amount, tax, VAT
   - Sinhala: විස්තරය, ප්‍රමාණය, ඒකක මිල, මුළු, බදු, වැට්
4. **Header→row binding (x-axis)** — assign each data token to nearest header x-center; ambiguous →
   `unknown_column`.
5. **Serialization (templates only)**:
   - LineItem: `LineItem | Description: {desc} | Qty: {qty} | UnitPrice: {unit_price} | Total: {total}`
   - KeyValue: `KeyValue | {key}: {value}`
   - Header: `Headers | {col1} | {col2} | ...`

## Chunking strategy

- `row_count ≤ 30` → one chunk per row.
- else → blocks of 5–10 rows per chunk, **repeat the header inside each block**.

## Failure handling

| Case | Fallback |
|---|---|
| No header detected | positional row chunks only |
| Sparse/shifted columns | `unknown_column`; preserve token order |
| Skew breaks clustering | raise threshold; optionally deskew upstream |
| ROI detection fails | skip ROI, full-page clustering |

**Rule: never drop tokens** — always emit best-effort chunks + provenance.

## Canonical-field mapping

Map Sinhala/English headers to C3 canonical keys where possible:
`item, description, qty, unit_price, total, tax, discount, currency, doc_date, vendor`.

## Metrics

Cell-extraction accuracy, 100% schema validity, association accuracy (number ↔ correct header).

## Implementation notes (Iter 3)

- `backend/spatial_serialization.py`: `cluster_rows` (step 2), `detect_header_row` (step 3),
  `bind_row_to_headers` (step 4), and the `serialize_*` template functions + `build_spatial_chunks`
  (step 5, top-level entry point) — consumes the same `final_safe_boxes.json` shape C1
  (`ocr_correction.write_final_safe_boxes`) produces.
- **Table-cell expansion moved into `ocr_service.py`.** Surya v2 gives one block (one bbox) per
  detected table — the algorithm above assumes per-token geometry, which a single table-wide bbox
  can't supply. `boxes_from_surya_v2_page` now expands `Table` blocks into one canonical box per
  cell (`table_block_to_cell_boxes`), with a synthetic bbox from a uniform grid over the block's
  bbox (an approximation — Surya v2 doesn't expose real per-cell coordinates) and `table_id` /
  `row_index` / `col_index` carried on each cell box. This is a shared C1/C2 change: C1 now
  corrects at cell granularity for tables too, and C2 gets real per-cell geometry to cluster.
- **Header keyword matching uses word boundaries**, not bare substring containment — a naive
  substring check on a short keyword like `"no."` false-positives inside unrelated words (e.g.
  `"now"`). `_match_header_keyword` anchors with `(?<!\w)...(?!\w)`.
- **Unmapped headers keep their original text as the field key** rather than failing — e.g. the
  mock fixture's Sinhala header `සේවාව` ("service") isn't in the canonical-field keyword list
  (component-2.md's Sinhala list only covers `විස්තරය/ප්‍රමාණය/ඒකක මිල/මුළු/බදු/වැට්`), so
  `bind_row_to_headers` falls back to the header's own text as the dict key instead of
  `unknown_column`. This still satisfies "never drop tokens" with better provenance than a bare
  positional fallback.
- Row clustering currently runs once across all boxes on a page, not per `table_id`. Two tables
  sharing a y-range on the same page would need per-table clustering first — tracked as an
  Iteration 3 follow-up in `docs/ROADMAP.md` (not hit by the single-table mock fixture).
- **Wired live (Iter 9).** `document_pipeline.py` produces `final_safe_boxes` (C1) and
  `spatial_chunks.json` (C2); on confirm-save, `app.py::_post_save_enrich` runs
  `build_spatial_chunks` → `embed_rows` → `upsert_chunk_embeddings` (pgvector). Verified live:
  254 chunks embedded.

### Geometric table reconstruction (no table-detection model)

The table branch originally depended on `table_id`/`row_index`/`col_index`, which only Surya v2
emits. The live OCR is Surya v1 (`surya-ocr==0.17.1` via Colab) and emits no table structure at
all, so `header_table_id` was always `None`, the `in_header_table` gate never opened, and every
row under a detected header fell through to `section_text`. Live chunks: 254 total — 224
`section_text`, 18 `key_value`, 12 `header`, **0 line items** — headers were being found with
nothing ever bound beneath them.

`build_spatial_chunks` now reconstructs the table from raw OCR geometry when no `table_id` is
present. A detected header row anchors the column positions and the rows beneath it are bound with
the same `bind_row_to_headers` (x-center nearest column) the v2 path uses; the table stays open
until a stop condition fires (`_geometric_table_ends`):

| Stop condition | Rationale |
|---|---|
| **Summary row** (`is_summary_row`) | The totals block ends the table. Requires *both* a summary label (`total`/`subtotal`/`balance`/`බදු`/`මුළු`…) in one of the first two cells *and* a row narrower than the header — so a real line item like `Total station tripod \| 2 \| 45000`, which matches the keyword alone, stays in. |
| **Large vertical gap** | A row starting more than `median_text_height * 2.5` below the previous bound row is detached from the table. |
| **Column misalignment** (`row_aligns_to_headers`) | Under half the row's cells land on a column. A cell counts if it horizontally *overlaps* a header box (a wide description under a narrow "Description") or its center is within `column_tolerance` (= 0.6 × median header spacing, so it scales with the document's own columns). Single-cell rows never align. |

`is_table_header` gates the whole path: the header must have ≥2 cells resolving to ≥2 *distinct*
canonical fields. This is not hypothetical — on live data `detect_header_row` scores 1.0 on a shop
address (`No. 655, Chilaw Road, Negombo`, matching `no.`) and on a Sinhala grand-total line
(`මුළු එකතුව | 1.556.00`, matching `මුළු`). The guard rejects both, so geometric mode simply
doesn't engage rather than mis-binding a page.

This is a heuristic and is deliberately biased toward stopping early: a false stop costs one
`section_text` chunk, a false bind invents a line item. Unit tests in
`tests/test_iter3_spatial_serialization.py` cover each stop condition, the header guard, the
never-drop-tokens invariant, and that v2 `table_id` geometry still takes the original path
unchanged. Verified live: re-embedding R17 produced the first `line_item_row` chunks in the
database (`LineItem | Qty: 1 | Description: Front and rear brake cables | UnitPrice: 100.00 |
Total: 100.00`), retrievable through `vector_index.retrieve_top_k`.

When Surya v2 (with layout) is served, `table_id` reappears and the original branch takes over
automatically — the geometric path is the fallback, not a replacement.
