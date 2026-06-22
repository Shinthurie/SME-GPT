# Component 4 — Multi-Tenant Relationship Index (MT-RI)

> Adapted from `docs/Research Components sme gpt.pdf` (Research Component 4).
> Storage = **Supabase Postgres** (source of truth). NetworkX may be an optional in-memory cache,
> never the source of truth.

## Purpose

A tenant-isolated relationship index linking Documents ↔ Vendors, Documents ↔ Reference numbers
(PO/INV), and Documents ↔ Documents (Invoice references PO). Solves the "vector DB silo" problem
where related docs don't share vocabulary (a PO says "laptop"; the invoice says "Payment for PO-101").

- **Ingestion-time:** after C2 produces `spatial_chunks.json`.
- **Query-time:** expand scope / resolve links before C3.

## Design goals

Strict `tenant_id` isolation · Postgres persistence · auditable edges (page/bbox/chunk_id evidence) ·
**deterministic first** (regex + normalization before fuzzy) · conservative entity resolution (prefer
aliases over hard merges) · fast query-time expansion.

## SQL schema (Postgres)

```sql
-- entities: vendors, doc_refs, items, categories
CREATE TABLE IF NOT EXISTS entities (
  entity_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  entity_type TEXT NOT NULL,          -- vendor | doc_ref | item | category
  canonical_name TEXT NOT NULL,       -- normalized
  raw_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, entity_type, canonical_name)
);

-- aliases: keep fuzzy matches; do not always hard-merge
CREATE TABLE IF NOT EXISTS entity_aliases (
  alias_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  alias_text TEXT NOT NULL,
  score DOUBLE PRECISION,
  method TEXT NOT NULL,               -- normalize | fuzzy | manual
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- doc_links: edges doc→entity or doc→doc
CREATE TABLE IF NOT EXISTS doc_links (
  link_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  from_doc_id UUID NOT NULL,
  link_type TEXT NOT NULL,            -- HAS_VENDOR | REFERENCES | CONTAINS_ITEM | HAS_REF
  to_entity_id UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
  to_doc_id UUID,
  confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  evidence JSONB,                     -- {page, bbox, chunk_id, extracted_text, rule}
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((to_entity_id IS NOT NULL) OR (to_doc_id IS NOT NULL))
);
```
Plus indexes on `(tenant_id, …)` for `entities`, `entity_aliases`, `doc_links` (see research §6).
These tables are created in **Iteration 1** (schema) and populated in **Iteration 6** (logic).

## Ingestion pipeline

1. **Extraction targets** (from `spatial_chunks.json` `key_value`/`line_item_row`): vendor name,
   doc numbers (INV/PO), reference numbers ("Payment for PO-101"), optional items/categories.
2. **Normalization (Stage A, deterministic):**
   - Vendor: lowercase, strip punctuation, drop suffixes (ltd, pvt, plc, limited, company, co…),
     collapse whitespace. `"Singer Sri Lanka (Pvt) Ltd" → "singer sri lanka"`.
   - Reference regex: `PO[-\s#:]?\d+`, `INV[-\s#:]?\d+` → canonical `PO_000101`, `INV_000031`.
3. **Conservative fuzzy aliasing (Stage B):** only after normalization.
   - score ≥ 0.92 → attach as alias to existing entity
   - 0.85–0.92 → store alias, lower confidence (no merge)
   - < 0.85 → new entity
   - Never delete/overwrite originals; keep provenance.
4. **Edge creation** with evidence JSON: `HAS_VENDOR`, `HAS_REF`, `REFERENCES` (Invoice→PO doc if
   present, else →ref entity), optional `CONTAINS_ITEM`.

## Query-time APIs

- `expand_related_docs(tenant_id, doc_ids)` → original + related docs (e.g. PO → invoices referencing it)
- `filter_docs(tenant_id, vendor=None, ref=None, date_range=None)` → filtered doc ids
- `docs_containing_item(tenant_id, item, date_range=None)` (optional; else rely on vector DB)

## Alignment with C3 (no document scope)

1. SQL filters candidate docs by date.
2. C4 filters/expands by vendor / PO-INV refs / linked docs.
3. Vector retrieval runs within that doc set.
4. C3 computes deterministically.

## Failure handling

| Failure | Behavior |
|---|---|
| Vendor missing | skip `HAS_VENDOR` |
| Ref detected, target doc absent | link to ref entity (`HAS_REF`) |
| Ambiguous vendor match | store alias, avoid merge |
| Conflicting ref formats | normalize to canonical, store raw as alias |

## Metrics

Cross-document recall, answer-correctness uplift on linked queries, expansion precision, added latency.
Test queries: "Did we pay for PO-101?", "Payments related to Dell laptops?", "Singer invoices in January".
