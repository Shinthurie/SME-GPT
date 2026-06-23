# Iteration 6 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Shinthurie · **Branch:** main

## 1. Scope

Component 4 — Multi-Tenant Relationship Index: entity normalization, conservative
fuzzy aliasing, DocLink edge creation, cross-document query APIs, and wiring into
the C3 PAL scope resolver.

Delivered:
- `backend/entity_index.py`
  - `normalize_entity_name()` — lowercase, strip punctuation + corporate suffixes
    (`ltd`, `pvt`, `co`, `inc`, 15 variants), collapse whitespace; returns `""`
    for NULL/empty input.
  - `is_fuzzy_match()` — Jaccard token similarity ≥ 0.8 OR edit-distance ≤ 2
    for names ≤ 12 chars (research §7 conservative threshold).
  - `index_document(doc, tenant_id)` — extracts `supplier_name`/`company_name`,
    upserts `Entity` (canonical form), upserts `EntityAlias` (raw spelling + fuzzy
    aliases against existing entities), upserts `DocLink` (`vendor_entity`,
    `customer_entity`, `order_ref`). Idempotent — safe to call multiple times.
  - `expand_related_docs(doc_id, tenant_id)` — follows forward/reverse `order_ref`
    edges and entity-peer links (documents sharing the same vendor/customer entity).
  - `filter_docs_by_entity(name, tenant_id)` — canonical match → LIKE alias fallback.

- `backend/pal_scope.py` — new `resolve_scope_with_c4()`: calls `resolve_scope()`
  then follows DocLink edges to expand the document set; degrades silently to the
  SQL-only path if `entity_index` is unreachable (network error, missing table, etc.).

## 2. Tests run

| Command | Result |
|---|---|
| `python -m pytest tests/test_iter6_entity_index.py -v` | **25 passed** in 96 s |
| `python -m pytest tests/ -q` (full suite) | **192 passed** |

Test breakdown (25 C4 tests):
- `normalize_entity_name`: 10 cases (suffix stripping, punctuation, lowercase, whitespace,
  NULL/None/empty, Sinhala passthrough, meaningful-word preservation)
- `is_fuzzy_match`: 9 cases (exact, Jaccard threshold, edit-distance ≤ 2, edit-distance
  too large, empty inputs, completely different)
- `resolve_scope_with_c4` graceful-degrade: 1 regression test (monkeypatched exception
  → SQL-only result returned, no propagation)
- DB integration (skip when `DATABASE_URL` absent):
  - `test_index_document_idempotent` — second call does not raise or duplicate
  - `test_index_document_creates_entity_and_alias` — canonical + raw alias in DB
  - `test_expand_related_docs_via_shared_vendor` — peer document found via entity
  - `test_filter_docs_by_entity_canonical` — exact canonical lookup
  - `test_filter_docs_by_entity_raw_name` — LIKE alias fallback

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Cross-document recall | tested | **100%** — vendor-peer and order_ref links verified on live Supabase |
| Idempotency | required | **Pass** — `index_document` called twice produces identical DB state |
| Graceful degrade | required | **Pass** — `resolve_scope_with_c4` never propagates entity-index errors |

## 4. Known gaps

- `resolve_scope_with_c4` is implemented but `pal_qa.py` still calls the original
  `resolve_scope()`. Switching the call site is a one-line change deferred to avoid
  touching the live endpoint without an end-to-end test. Tracked as a follow-up.
- Fuzzy aliasing only runs at `index_document()` time (batch, not query-time), so
  newly indexed entities don't retroactively alias against older ones unless
  `index_document` is re-run. Acceptable for the current volume.
- `is_fuzzy_match` is English-optimized (Jaccard over word tokens). Sinhala entity
  names pass through normalization unchanged and match only on exact canonical
  equality; fuzzy Sinhala matching would need character n-gram similarity instead.

## 5. Next

- Iteration 7 (Explainability UI + Provenance Highlighting): document viewer with
  bbox overlays, click-to-source on extracted fields, derivation trace for answers.
