# SME-GPT — Frontend

Next.js 16 (App Router) · React 19 · TypeScript 5 · Tailwind CSS 4 · Prisma 7.

The web client for SME-GPT: upload documents, review extracted data with bbox/provenance overlays,
ask natural-language financial questions, and manage the repository, workflow and account settings.
Talks to the FastAPI backend (default `http://127.0.0.1:8000`) and to its own Next.js API routes for
auth/session concerns.

## Getting started

```bash
npm install
cp .env.example .env        # NEXT_PUBLIC_BACKEND_URL, DATABASE_URL, NEXTAUTH_SECRET, SMTP_*
npx prisma generate
npm run dev                 # http://localhost:3000
```

Useful scripts: `npm run build` (production build / typecheck of all routes), `npx tsc --noEmit`
(typecheck only), `npm run lint`.

## How it's organised

- `src/app/*` — App-Router pages. Backend mapping: `/analysis/[documentID]` (process → confirm →
  edit), `/query` → `/answer`, `/repository`, `/dashboard`, plus auth/admin/profile/session pages.
- `src/app/api/*` — Next.js route handlers for auth, sessions, admin and profile (these use Prisma).
- `src/lib/i18n.ts` — the English/Sinhala dictionary. **Both `ui.en` and `ui.si` must stay key-for-key
  in sync**; every user-facing string goes through it (no hardcoded copy in pages).
- `src/lib/notifications.ts` / `src/lib/overdueAlerts.ts` — client notification store + overdue sync.
- `src/components/layout/*` — `MobileShell`, `BottomNav`, `LanguageSwitcher`, `ThemeToggle`.

## Theming & i18n

- **Dark mode**: CSS variables under `:root` and `[data-theme="dark"]` in `src/app/globals.css`.
  Always style with the `--bg` / `--surface` / `--text-*` / `--brand*` tokens, not hardcoded hex,
  so both themes work. The theme is applied pre-paint by an inline script in `src/app/layout.tsx`.
- **Language**: stored in `localStorage['sme_gpt_language']`; read via `getStoredLanguage()`. Pages
  set a local `lang` state on mount and render `ui[lang].<key>`.

> Note: this app targets a newer Next.js than most tooling assumes — see `AGENTS.md` before relying
> on conventions from older Next.js versions.
