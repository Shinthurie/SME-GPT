# Contributing to SME-GPT

This guide is the team workflow for Ashfak and Shinthurie. Keep it simple and follow it every time.

## 1. Branching

- `main` is **protected** — never push directly.
- Create a short-lived branch off `main`:
  - `feat/<short-name>` — new feature
  - `fix/<short-name>` — bug fix
  - `docs/<short-name>` — docs only
  - `refactor/<short-name>` / `test/<short-name>` — as named
- Keep branches small and focused on one issue.

```bash
git checkout main && git pull
git checkout -b feat/c1-numeric-safeguard
```

## 2. Commits

Use **Conventional Commits**:

```
feat(c1): add safe_correct numeric safeguard
fix(api): correct tenant filter on /documents
docs: add architecture diagram
test(c3): add arithmetic accuracy harness
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.
Scope is optional (`c1`..`c4`, `api`, `db`, `ui`).

## 3. Pull Requests

1. Push your branch and open a PR into `main`.
2. Fill in the PR template (what/why/how-tested/screenshots).
3. **CI must be green** (backend `pytest`+`ruff`, frontend `eslint`+`tsc`+`build`).
4. **The other person reviews** before merge (the area owner reviews their area).
5. Squash-merge; delete the branch.

If you changed an API endpoint, update `API_CONTRACT.md` **in the same PR**.

## 4. Issues & board

- One **issue per task**. Title is imperative ("Migrate dataset_manager to Postgres").
- Labels: component (`C1`..`C4`), layer (`backend`/`frontend`/`db`), iteration (`iter-0`..).
- Assign a **primary owner** (reassignable). Move the card across the board as you work.

## 5. Local setup

### Backend
```bash
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn app:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env   # fill in values
npx prisma generate
npm run dev   # port 3000
```

## 6. Before you push (local checks)

```bash
# backend
cd backend && ruff check . && pytest
# frontend
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

## 7. Per-iteration definition of done

An iteration is done only when:
- [ ] Code + tests written and passing
- [ ] `docs/test-reports/iteration-N.md` written
- [ ] `docs/ROADMAP.md` checkboxes ticked
- [ ] `docs/gap-analysis.md` updated
- [ ] PR reviewed by the other member and merged on green CI

## 8. Secrets

Never commit `.env`, API keys, or credentials. Use `.env.example` for documented placeholders.
`backend/.env` and `frontend/.env` are gitignored.
