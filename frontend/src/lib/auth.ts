export type SessionUser = {
  id: string;
  email: string;
  fullName: string;
  companyName?: string;
  token?: string;
};

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
  const res = await fetch("/api/auth/me", {
    method: "GET",
    cache: "no-store",
  });

  if (!res.ok) return null;

  const data = await res.json();
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
  localStorage.removeItem("token");
  sessionStorage.removeItem("token");

  await fetch("/api/auth/logout", {
    method: "POST",
  });
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