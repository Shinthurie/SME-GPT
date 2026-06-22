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
