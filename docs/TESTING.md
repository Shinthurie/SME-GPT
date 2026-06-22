# SME-GPT — Testing Strategy

We test **after every iteration** and record results in `docs/test-reports/iteration-N.md`.
Tests are part of "done," not an afterthought. No rush — correctness over speed.

## 1. Test layers

| Layer | Tooling | Scope |
|---|---|---|
| Backend unit | `pytest` | pure functions: numeric safeguard, row clustering, plan validator, normalization |
| Backend integration | `pytest` + test DB | DB CRUD, tenant isolation, FastAPI endpoints (`TestClient`) |
| Component evaluation | `pytest` + eval harness | research metrics per component (see §3) |
| Frontend static | `eslint`, `tsc --noEmit`, `next build` | lint, types, build |
| Frontend UI | component / e2e tests | viewer overlays, click-to-source, query flow |
| End-to-end | manual + scripted | upload → extract → save → query → answer-with-citation |

## 2. How to run

```bash
# Backend
cd backend
ruff check .
pytest -q                 # all tests
pytest tests/test_c1.py   # one module

# Frontend
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Existing backend tests live as `backend/test_*.py`; new tests go under `backend/tests/` as we grow.

## 3. Research evaluation metrics (per component)

These prove the research claims and feed the academic evaluation / viva.

| Component | Metric | Target |
|---|---|---|
| C1 OCR correction | CER (character error rate) | < 5% |
| C1 numeric safety | NAR (numeric accuracy rate) | = 100% |
| C1 | unsafe-block rejection rate | tracked |
| C2 serialization | cell-extraction accuracy, schema validity | high; 100% schema-valid |
| C4 retrieval | cell-query retrieval hit-rate | beats naive chunking baseline |
| C4 linking | cross-document recall | beats vector-only baseline |
| C3 PAL | arithmetic accuracy vs ground truth | ~100% on supported ops |
| C3 | plan success rate, association accuracy | tracked |
| All | provenance success rate (valid bbox) | high |

Each eval harness loads a small labelled set from `backend/sample_docs/` (and a growing fixtures
folder), runs the component, and asserts the metric against its target.

## 4. Test data

- `backend/sample_docs/` — sample invoices/POs/receipts (English + Sinhala).
- Add a `backend/tests/fixtures/` folder with small JSON ground-truth files
  (expected fields, expected totals, expected chunk schema) as components land.
- Never use real customer data in fixtures.

## 5. Test report format (`docs/test-reports/iteration-N.md`)

Each report records:
1. **Scope** — what was built this iteration.
2. **Tests run** — commands + summary (pass/fail counts).
3. **Metrics** — relevant research metrics with numbers.
4. **Failures / known gaps** — what's not covered yet.
5. **Next** — follow-ups carried forward.

A template is provided at `docs/test-reports/_template.md`.

## 6. CI

`.github/workflows/ci.yml` runs backend (`ruff`, `pytest`) and frontend (`eslint`, `tsc`, `build`)
on every PR. Merges to `main` are blocked unless CI is green.
