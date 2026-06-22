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
- **Not yet wired into `document_pipeline.py`** — same status as C1 (Iter 2): both are standalone,
  tested modules pending a real OCR engine and the decision to replace the live whole-text-blob
  extraction flow.
