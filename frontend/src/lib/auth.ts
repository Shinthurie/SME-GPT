export type SessionUser = {
  id: string;
  email: string;
  fullName: string;
  companyName?: string;
  role?: string;
  token?: string;
};

/* ── Session cache ──────────────────────────────────────────────────────────
   Every page independently awaited /api/auth/me on mount, and the bottom nav
   made a second call of its own — so switching tabs meant a network round trip
   before anything could render, and pages that gate on `session` showed a bare
   body background for its duration. That's the blank flash between tabs.

   The cache is module-level, so it lives as long as the tab does and is gone
   after any full reload. Reads are stale-while-revalidate: a warm cache answers
   instantly and refreshes in the background, so a tab switch renders with zero
   latency while still noticing a session that changed underneath it. */
let cachedUser: SessionUser | null = null;
let cachedAt = 0;
let inflight: Promise<SessionUser | null> | null = null;

/** Considered fresh enough to skip even a background refresh. */
const FRESH_MS = 30_000;

/**
 * The session if one has already been loaded in this tab, without a fetch.
 * Lets a page seed its initial state and render real content on the very first
 * paint instead of gating on an effect. Null means "not known yet", never
 * "logged out" — call getSession() for that.
 */
export function peekSession(): SessionUser | null {
  return cachedUser;
}

/** Drops the cache so the next read re-fetches. Call after anything that
 *  changes who you are or what your profile says. */
export function invalidateSession() {
  cachedUser = null;
  cachedAt = 0;
}

export async function loginUser(email: string, password: string) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  const data = await res.json().catch(() => ({}));

  if (res.ok && data?.token) {
    localStorage.setItem("token", data.token);
  }

  return {
    ok: res.ok,
    data,
  };
}

export async function signupUser(data: {
  fullName: string;
  companyName: string;
  email: string;
  password: string;
}) {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  return res.ok;
}

export async function getSession(): Promise<SessionUser | null> {
  const age = Date.now() - cachedAt;
  if (cachedUser && age < FRESH_MS) return cachedUser;
  if (cachedUser) {
    // Stale: hand back what we have immediately and refresh behind it. The
    // caller renders now; the next read sees the updated value.
    void revalidateSession();
    return cachedUser;
  }
  return revalidateSession();
}

/** Coalesces concurrent callers onto one request — several components mounting
 *  together must not each fire their own /api/auth/me. */
function revalidateSession(): Promise<SessionUser | null> {
  if (inflight) return inflight;
  inflight = fetchSession()
    .then((user) => {
      cachedUser = user;
      cachedAt = Date.now();
      return user;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

async function fetchSession(): Promise<SessionUser | null> {
  const res = await fetch("/api/auth/me", {
    method: "GET",
    cache: "no-store",
  });

  if (!res.ok) return null;

  const data = await res.json();

  // The httpOnly cookie (checked server-side by /api/auth/me) is the source
  // of truth for whether you're logged in. localStorage is a separate copy
  // used for direct Bearer-token calls to the FastAPI backend, and can be
  // empty even with a valid cookie session (e.g. the login page redirects
  // straight to /dashboard when the cookie is still valid, skipping the
  // login form that would normally set it). Re-sync it here whenever the
  // server hands back a token, so it never falls out of sync with the
  // cookie that's actually authenticating you.
  if (typeof window !== "undefined" && data.token) {
    localStorage.setItem("token", data.token);
  }

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("token") || sessionStorage.getItem("token") || ""
      : "";

  return {
    ...data.user,
    token,
  };
}

export async function logoutUser() {
  invalidateSession();
  localStorage.removeItem("token");
  sessionStorage.removeItem("token");

  await fetch("/api/auth/logout", {
    method: "POST",
  });

  // Leave via a real document navigation rather than router.push(), for two
  // reasons: replace() drops the page we're leaving from the history stack so
  // Back can't return to it, and a full load discards the client router cache
  // holding the rendered dashboard (and the React state with the previous
  // user's figures in it). Callers should not navigate after awaiting this.
  if (typeof window !== "undefined") {
    window.location.replace("/login");
  }
}

export function clearAllDummyAuth() {
  localStorage.removeItem("dummyUser");
  localStorage.removeItem("token");
  localStorage.removeItem("isLoggedIn");
  sessionStorage.removeItem("token");
}

export function getStoredToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}