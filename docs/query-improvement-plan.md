# Plan: Make querying fast & accurate (English + Sinhala) — quick win

> Status: PROPOSAL — not implemented. Reference doc for later.

## Context

Querying feels slow and inaccurate. Root cause is **not** the deterministic parts
(the `normalize_query` dictionary and the pandas arithmetic are correct by design and
must stay). The weak links are:

1. **Query plan/answer quality** comes from local `sme-gpt-llama3` — a small CPU model
   with a 600s timeout. This is why the planner produced `lookup_value` instead of
   `aggregate_sum` (the LKR 125,000→100,000 bug) and why Sinhala phrasings misfire.
2. **`call_llm` never caches** (`llm_client.py:197` docstring: "Responses are NOT cached
   here"), so every query re-runs the planner **and** answer LLM from scratch — even
   identical repeats.

`llm_client.py` **already fully supports Gemini** via direct REST (no SDK/new deps), with
automatic fallback to Ollama. So the highest-impact fix is mostly configuration: route
**query** tasks to **Gemini 2.5 Flash** (fast + natively strong in Sinhala), then add
response caching. The OCR pipeline (Surya OCR → DeepSeek correction/extraction) is left
untouched.

**Decisions taken:** Query LLM = Gemini 2.5 Flash · Scope = quick win (switch + cache) ·
OCR pipeline unchanged (Surya is the OCR model; DeepSeek only corrects/extracts).

## Changes

### 1. Enable Gemini for query tasks — config only, no code
In `backend/.env`:
```
GEMINI_API_KEY=<key>
# gemini-2.5-flash is already the default GEMINI_MODEL; QUERY_LLM_PROVIDER auto-selects
# "gemini" once the key is present (llm_client.py:83). Set explicitly if desired:
QUERY_LLM_PROVIDER=gemini
```
No code change: `call_llm()` (`llm_client.py:204`) already tries Gemini first and falls
back to Ollama on any error or missing key. `sme-gpt-llama3` stays as the offline fallback
automatically. Pipeline (DeepSeek) config stays as-is.

### 2. Add response caching to `call_llm` — `llm_client.py:197-217`
Reuse the existing in-process cache infra already used by `call_pipeline_llm`
(`_cache_key`, `_cache_get`, `_cache_set`, TTL via `LLM_CACHE_TTL_SECS`). Wrap the
Gemini+Ollama routing: check cache first; on a successful response, store it.
- Update the misleading docstring line ("Responses are NOT cached here").
- **Why it's safe (no stale answers):** the planner prompt encodes the question (+ today's
  date + any retry_note), so plans are cache-keyed on their real inputs and retries differ;
  the answer prompt encodes the `computed` JSON, so if underlying data changes the computed
  result changes and the key changes. Identical inputs → identical output, which is exactly
  what we want to cache. Retry attempts use different prompts, so caching never short-circuits
  the retry loop.

### 3. Test the cache — `backend/tests/test_iter21_quickwins.py`
- Add a test: two identical `call_llm(prompt, system)` calls invoke the underlying provider
  **once** (second served from cache). Clear `llm_client._CACHE` at the start of the test for
  isolation.
- Existing `test_call_llm_passes_json_format` / `test_call_llm_omits_format_by_default` use
  distinct (prompt, system) keys, so they keep passing; if any flakiness appears, add a
  cache-clearing autouse fixture in that module.

## Out of scope (explicitly not doing now)
- Loosening the `route_question` keyword router / broadening PAL coverage (deferred — the
  Gemini upgrade already makes misrouting far less damaging).
- Any change to Surya OCR or the DeepSeek correction/extraction pipeline.
- A Sinhala eval harness (deferred with the routing overhaul).

## Verification
1. Set `GEMINI_API_KEY`, restart backend (`uvicorn app:app --reload --port 8000`).
2. Run these in the app and check backend logs show `[LLM] Gemini query call in Xs`
   (should be ~1-3s, not minutes):
   - EN: `what's the total receivable we have?` → expect **LKR 125,000** via `aggregate_sum`.
   - EN: `how much do we owe "Lanka Beverage Supplies"?` → expect **LKR 16,500**.
   - SI: `ලැබිය යුතු කීයද` (receivable) and `ගෙවිය යුතු කීයද` (payable) → correct totals,
     fluent Sinhala answer.
3. Re-run the same query twice; second run logs a cache hit / returns instantly.
4. Kill/omit the key → confirm it still works via Ollama fallback (graceful degradation).
5. `./venv/Scripts/python.exe -m pytest tests/test_iter5_pal_qa.py tests/test_iter21_quickwins.py -q`
   — all green, including the new cache test.

## TL;DR
- **Biggest lever:** point query planning/answering at Gemini 2.5 Flash (already supported;
  just needs `GEMINI_API_KEY`). Faster than CPU llama3 and fluent in Sinhala.
- **Second lever:** cache `call_llm` responses so repeat queries are instant.
- **Keep:** deterministic arithmetic + Sinhala dictionary (the reliable parts).
- **Later (if still needed):** loosen keyword routing, add a Sinhala eval set, consider
  Gemini for Sinhala OCR extraction.
