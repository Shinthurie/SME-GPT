# SME-GPT — Work Division

Two contributors: **Ashfak** and **Shinthurie**. We split by **layer**, but ownership is
**flexible, not a wall**.

## What "ownership" means

The owner is **responsible** for the area: its design, that tasks get done, and reviewing PRs that
touch it. Ownership does **not** mean only the owner may write that code. When one person is
blocked, ahead of schedule, or unavailable, **the other crosses the boundary and helps** — e.g.
Ashfak may implement frontend/DB tasks, and Shinthurie may implement backend tasks. The area owner
still reviews the resulting PR so knowledge stays shared. Pairing on hard tasks is encouraged.

## Primary ownership

### Ashfak — Backend + AI/ML (`backend/`)
- OCR service wrapper (`OCRService`, Surya colab/local)
- Component 1 (semantic OCR correction + numeric safeguard)
- Component 2 (spatial serialization)
- Component 3 (PAL planner / validator / executor / answer generator)
- Component 4 pipeline logic (normalization, aliasing, edges, query APIs)
- DeepSeek integration, vector indexing & retrieval
- FastAPI endpoints, backend `pytest` suites
- Docs: `ARCHITECTURE.md`, `docs/components/*`

### Shinthurie — Frontend + DB + UX (`frontend/`, schema)
- Supabase schema & migrations; C4 table DDL
- Prisma models / data-access layer
- All Next.js pages (dashboard, upload, analysis, query, repository, profile, auth)
- Explainability UI: document viewer, bbox overlays, click-to-source, derivation trace
- i18n (English/Sinhala), design system, RBAC UI
- Frontend tests (lint/type/build, component/e2e)

### Shared / either person
- Iteration 0 setup, CI/CD, linters
- `API_CONTRACT.md` (the backend↔frontend boundary)
- Integration tests, `gap-analysis.md`, security hardening (Iter 8)
- Any cross-boundary help, as above

## Ownership matrix (RACI-lite)

| Area | Primary (R) | Reviewer (A) | Helps when needed |
|---|---|---|---|
| Repo/CI/docs setup | Shared | Either | Both |
| DB schema & migrations | Shinthurie | Shinthurie | Ashfak |
| OCR + C1/C2/C3/C4 logic | Ashfak | Ashfak | Shinthurie |
| Vector index & retrieval | Ashfak | Ashfak | Shinthurie |
| FastAPI endpoints | Ashfak | Ashfak | Shinthurie |
| Frontend pages & UX | Shinthurie | Shinthurie | Ashfak |
| Explainability UI | Shinthurie | Shinthurie | Ashfak |
| Security/RBAC | Shared | Both | Both |

## The boundary: `API_CONTRACT.md`

Because we work in parallel, the JSON request/response shapes in `API_CONTRACT.md` are the agreed
contract. Any endpoint change updates that file **in the same PR**. As long as the contract holds,
either side can develop and test independently (the frontend can mock; the backend has `pytest`).

## How tasks are assigned

- One **GitHub issue per task**, with a **primary owner** named — but issues can be reassigned freely.
- Labels: component (`C1`..`C4`), layer (`backend`/`frontend`/`db`), iteration (`iter-0`..`iter-8`).
- The Project board tracks Backlog → In Progress → In Review → Done.
