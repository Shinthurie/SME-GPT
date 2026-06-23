# Iteration 13 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Ashfak · **PR:** (feat/iter-13-deskew-errors)

## 1. Scope

Deskew Preprocessing (GAP-F) + Standardised Error Handling (GAP-I), per
`docs/iteration-plan-9-14.md`. Independent of Iterations 9-12; runs entirely in `backend/`.

Delivered:

### Deskew (`backend/document_pipeline.py`)
- Added `deskew` to `backend/requirements.txt`.
- `_deskew_image(img: np.ndarray) -> np.ndarray` — `determine_skew()` (grayscale) finds the skew
  angle; `cv2.getRotationMatrix2D` + `cv2.warpAffine` (same-size canvas, `BORDER_REPLICATE` so the
  rotated corners don't introduce black wedges) corrects it. Angles under 0.3deg are treated as
  noise and left untouched — `determine_skew()` never returns exactly 0 even for a dead-straight
  scan, so rotating a near-zero angle would just re-sample the image (a quality loss) for nothing.
- Wired into `preprocess_images()` immediately after `cv2.imread()`, before the 1600px resize — so
  both the "P" (printed) and "M" (messy) downstream variants get the corrected image.

### Standardised errors (`backend/app.py`)
- `ErrorResponse(BaseModel)`: `success: bool = False`, `error_code: str`, `message: str`.
- `@app.exception_handler(HTTPException)` — maps `status_code` to `error_code` via
  `_ERROR_CODE_BY_STATUS` (`400→BAD_REQUEST`, `401→UNAUTHORIZED`, `403→FORBIDDEN`,
  `404→DOCUMENT_NOT_FOUND`, `409→CONFLICT`, `429→RATE_LIMITED`, anything else → `HTTP_{status}`).
- `@app.exception_handler(Exception)` — logs the full traceback server-side
  (`traceback.print_exc()`), returns 500 with `error_code="INTERNAL_ERROR"` and a fixed generic
  message. `str(exc)` is **never** included in the response body.
- Removed all 15 per-route `except HTTPException`/`except Exception` blocks that manually
  rebuilt `{"success": false, "message": ...}` JSON (and, for the generic case, leaked `str(e)` —
  e.g. `f"Error while saving document: {str(e)}"`, which could surface SQL fragments or file
  paths). Routes now just `raise HTTPException(...)` for expected error conditions (404s, 400s,
  ownership checks) and let any other exception propagate to the new global handler. `finally`
  blocks (temp-dir cleanup in `/process-document`) and the SSE error-event path inside
  `/process-document-stream`'s background thread (a different mechanism — it emits over the
  stream, not an HTTP error response) were left untouched.

### Tests: `backend/tests/test_iter13_deskew_errors.py`
- 6 tests (plan asked for 5; added one more for the 403 path since RBAC denials are the most
  common error in this app and worth locking the error_code for).

## 2. Tests run

| Command | Result |
|---|---|
| `cd backend && python -m pytest tests -q` | **260 passed** (full suite — 254 from before + 6 new) |
| `python -c "import app"` | imports cleanly, no syntax/import errors after removing the per-route try/except blocks |
| Manual `_deskew_image()` sanity check (straight + 5deg-rotated synthetic image) | straight image returned byte-identical; rotated image's residual skew angle reduced after correction |

New tests cover:
- `_deskew_image`: a perfectly straight synthetic image is returned unchanged (no resampling);
  a 5deg-rotated synthetic image (rows of black bars standing in for text lines — `determine_skew`
  needs line structure, not a blank canvas) has its residual skew angle reduced after correction.
- `ErrorResponse`: `model_dump()` produces exactly `{success, error_code, message}`.
- Global `Exception` handler: a route's dependency is monkeypatched to raise
  `RuntimeError("secret_path/db_connection_string_leak")`; the response is the fixed generic
  `INTERNAL_ERROR` body and the leaked string never appears anywhere in the response text.
- `404` → `DOCUMENT_NOT_FOUND`, `403` (RBAC denial) → `FORBIDDEN` — both verified against the real
  routes (`GET /documents/{id}`, `DELETE /documents/{id}`), not a parallel reimplementation.

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Error response consistency | every error returns `{success:false, error_code, message}` | **verified** for HTTPException (4xx) and unhandled (5xx) paths via the two global handlers; all 15 previously-bespoke per-route error blocks removed |
| No internal detail leakage | 500 responses never include `str(exception)` | **verified** — the hermetic test injects a message containing a fake leaked path/secret and confirms it's absent from the response |
| Deskew correctness | rotated input's residual skew reduced after correction | **verified** on a synthetic 5deg rotation; no live-document fixture available in this environment (no scanner/phone photo on hand) — flagged below |

## 4. Known gaps

- **No real rotated-document fixture tested.** The deskew unit tests use synthetic numpy images
  (black bars on white) since `determine_skew()` needs line-like structure, not a blank canvas —
  this proves the function's logic but not how well it performs on an actual noisy phone photo.
  The user has a sample receipt photo to test manually post-merge; if it reveals the threshold or
  border-fill choice needs tuning, that's a quick follow-up, not a redesign.
- **`_emb_err`-style inner `try/except`s inside route bodies are untouched** (e.g. the
  best-effort embedding/persist block in `/confirm-save`, the `history_saved` fallback in
  `/ask-query`) — these are deliberate "this part is optional, don't fail the whole request"
  patterns, not part of GAP-I's scope (which is about the *outermost* per-route error shape).
- **`_ERROR_CODE_BY_STATUS` has a small fixed set.** Any `HTTPException` raised with a status code
  not in the map falls back to `HTTP_{status}` (e.g. a future `409` use already has `CONFLICT`,
  but an unanticipated code like `422` would surface as `HTTP_422`) — acceptable for now, easy to
  extend when a new status code is actually used.

## 5. Next

- Iteration 14 (PWA support) is independent and can start now.
- The deskew threshold (0.3deg) and `BORDER_REPLICATE` fill choice should be revisited once tested
  against a real phone-photo document rather than only synthetic images.
