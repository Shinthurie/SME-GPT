# Iteration 14 — Test Report

**Date:** 2026-06-23 · **Owner(s):** Ashfak · **PR:** (feat/iter-14-pwa)

## 1. Scope

PWA Support (NFR-08), per `docs/iteration-plan-9-14.md`. Independent of every other iteration;
frontend-only.

**Deviation from the written plan, confirmed with the user first:** the plan specifies
`@ducanh2912/next-pwa`. That package is a **webpack plugin** (it wraps `webpack()` in
`next.config.js` to run Workbox). This project builds with **Turbopack** (the Next.js 16 default —
confirmed via `node_modules/next/dist/docs/01-app/03-api-reference/08-turbopack.md`: *"Turbopack
does not support webpack plugins"*). Wiring in `next-pwa` as written would silently produce no
service worker under the actual `npm run build` command, failing the plan's own exit criteria.
Two options were considered: force `next build --webpack` just for `next-pwa` (forks the build
pipeline off Turbopack for one plugin, fragile long-term), or hand-write a minimal service worker
(no Workbox precaching, but fully Turbopack-compatible, zero pipeline changes). Went with the
hand-written option — picked with the user before implementing.

Delivered:

### Files added
- `frontend/public/manifest.json` — name/short_name/start_url (`/dashboard`)/display/colors/icons,
  matching the plan's manifest exactly.
- `frontend/public/icons/icon-192.png`, `icon-512.png` — generated (no existing brand logo in the
  repo to reuse) via Pillow: brand-blue (`#2563ff`) background with a white "document + lines"
  glyph; the 512px one is the `maskable` variant with extra safe-zone padding per the manifest
  spec.
- `frontend/public/sw.js` — hand-written service worker. Precaches only the app shell
  (`manifest.json` + the two icons) on install; cache-first for those exact assets; explicitly
  ignores `/api/*` and `/_next/data/*` so no financial data (documents, query answers) is ever
  served stale from a service-worker cache — important for a financial app, where a cached "amount
  owed" while offline would be misleading rather than helpful.
- `frontend/src/components/PwaRegister.tsx` — client component, registers `/sw.js` on mount, only
  in production (skips in `next dev` to avoid dev-cache confusion, same intent as the plan's
  `disable: process.env.NODE_ENV === "development"` for `next-pwa`).

### Files modified
- `frontend/src/app/layout.tsx` — `metadata.manifest`, `metadata.icons.apple`,
  `metadata.appleWebApp` (capable + title), and a separate `viewport` export for `themeColor`
  (the plan's `metadata.themeColor` is deprecated as of Next.js 14 — confirmed in
  `generate-metadata.md` — moved to `generateViewport`/`viewport` per current Next.js docs).
  Renders `<PwaRegister />` once in `<body>`.

## 2. Tests run

| Command | Result |
|---|---|
| `cd frontend && npx tsc --noEmit` | 0 errors |
| `cd frontend && npm run build` | Compiled successfully, all 41 routes built |
| `next start` (production mode) + `curl` against the running server | `/manifest.json` → 200, `/sw.js` → 200, `/icons/icon-192.png` + `/icons/icon-512.png` → 200; `<head>` on `/login` confirmed to contain `rel="manifest"`, `name="theme-color" content="#2563ff"`, `name="mobile-web-app-capable" content="yes"`, `name="apple-mobile-web-app-title"`, `rel="apple-touch-icon"` |

No backend changes in this iteration — `backend/tests` suite untouched (still 260 passing from
Iteration 13).

## 3. Metrics

| Metric | Target | Measured |
|---|---|---|
| Manifest + icons served | reachable at the paths the manifest references | **verified** via `curl` against a real `next start` server |
| Head metadata present | manifest link, theme-color, apple web-app tags | **verified** by inspecting rendered `<head>` output |
| Service worker registers | `/sw.js` reachable, registration code present | **verified** file is served correctly; actual browser registration (DevTools → Application → Service Workers) not checked in this environment (no GUI browser available here) — flagged below |
| `tsc --noEmit` / `npm run build` | clean | **0 errors / compiles successfully** |

## 4. Known gaps

- **No browser-based verification of service worker registration or installability.** This
  environment has no GUI browser to drive DevTools or run a Lighthouse PWA audit. `curl`-level
  checks confirm every asset is served and the right `<head>` tags are present, but the user
  should confirm in Chrome DevTools (Application → Manifest / Service Workers) and run a Lighthouse
  PWA pass before treating NFR-08 as fully closed.
- **No Workbox-style runtime caching strategies** (stale-while-revalidate for navigation, etc.) —
  the hand-written `sw.js` only precaches the static app shell (manifest + icons) and explicitly
  does not touch API responses or page navigations. This is a deliberate, smaller scope than
  `next-pwa` would have given, chosen for Turbopack compatibility; if the project later needs
  richer offline behavior (e.g. an offline fallback page for navigation), that would need to be
  hand-rolled too, since `next-pwa`/Workbox isn't an option under Turbopack.
- **Icons are generated placeholders**, not a real brand logo — the repo had no existing app icon
  to reuse. Swap `public/icons/icon-*.png` for real artwork whenever the project gets one; the
  manifest references won't need to change as long as the filenames stay the same.

## 5. Next

- This was the last iteration on `docs/iteration-plan-9-14.md`. All of Iterations 9–14 (GAP-A
  through GAP-I) are now done or at the documented partial status in `docs/gap-analysis.md`.
- Manual follow-ups before calling NFR-08 fully verified: Chrome DevTools manifest/SW check +
  Lighthouse PWA audit (both require a GUI browser, not available in this environment).
