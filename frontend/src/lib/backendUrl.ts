// Where the frontend should send API calls.
//
// NEXT_PUBLIC_* env vars are inlined at *build* time, so a Vercel deployment is
// pinned to whatever backend URL was set when it was built. That's a problem
// while the backend runs on a laptop behind an ephemeral tunnel (cloudflared
// quick tunnels get a new URL every restart) — it would mean re-deploying the
// frontend every session just to change one string.
//
// So the build-time env var is the *default*, and a value saved in localStorage
// overrides it. Paste the current tunnel URL into Settings once per session and
// no redeploy is needed. Once the backend has a permanent home (a VPS with a
// real domain), set NEXT_PUBLIC_BACKEND_URL to it and the override can stay
// empty forever.

const OVERRIDE_KEY = "sme_gpt_backend_url";

const ENV_DEFAULT = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

/** Trim whitespace and any trailing slashes so `${base}/path` never doubles up. */
function normalize(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

/** The saved override, or "" if unset (also "" during SSR). */
export function getBackendUrlOverride(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(OVERRIDE_KEY) ?? "";
  } catch {
    return ""; // private mode / storage disabled
  }
}

/** The build-time default, shown in the UI as a hint. */
export function getDefaultBackendUrl(): string {
  return normalize(ENV_DEFAULT);
}

/**
 * The backend base URL to call. Override first, else the build-time default.
 *
 * Callers read this at module scope. In a client component that module is
 * evaluated in the browser, so the override is picked up; during SSR there's no
 * localStorage and it falls back to the env default. The value is only ever
 * used in fetch() URLs and never rendered, so the two can differ safely without
 * a hydration mismatch.
 */
export function resolveBackendUrl(): string {
  const override = getBackendUrlOverride();
  return override ? normalize(override) : normalize(ENV_DEFAULT);
}

export function setBackendUrlOverride(url: string): void {
  if (typeof window === "undefined") return;
  try {
    const cleaned = normalize(url);
    if (cleaned) localStorage.setItem(OVERRIDE_KEY, cleaned);
    else localStorage.removeItem(OVERRIDE_KEY);
  } catch {
    /* storage disabled — nothing to do */
  }
}

export function clearBackendUrlOverride(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(OVERRIDE_KEY);
  } catch {
    /* storage disabled */
  }
}
