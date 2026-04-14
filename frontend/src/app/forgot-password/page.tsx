"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();
  setLoading(true);
  setMessage("");

  try {
    const res = await fetch("/api/auth/forgot-password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();

    if (!res.ok) {
      setMessage(data.error || "Something went wrong");
      return;
    }

    setMessage("Reset email sent. Please check your inbox.");
  } catch {
    setMessage("Request failed. Please try again.");
  } finally {
    setLoading(false);
  }
};
  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f7f8fb] px-4 py-8">
        <div className="mx-auto max-w-[520px] rounded-[30px] border border-[#d9dff0] bg-white p-8 shadow-sm">
          <h1 className="text-center text-[28px] font-extrabold text-[#0f172a]">
            Forgot Password
          </h1>

          <p className="mt-3 text-center text-[13px] text-[#64748b]">
            Enter your email to get a reset link
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <input
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white px-4 text-[15px] text-slate-900 outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
              required
            />

            <button
              type="submit"
              disabled={loading}
              className="flex h-12 w-full items-center justify-center rounded-2xl bg-[#07122f] text-[16px] font-bold text-white"
            >
              {loading ? "Creating..." : "Send Reset Link"}
            </button>
          </form>

          {message && (
            <p className="mt-4 text-[13px] text-center text-[#2563ff]">
              {message}
            </p>
          )}

          {resetLink && (
            <div className="mt-4 rounded-2xl bg-[#eef4ff] p-4 text-center">
              <p className="text-[12px] text-[#475569]">Test reset link:</p>
              <button
                onClick={() => router.push(resetLink)}
                className="mt-2 text-[13px] font-bold text-[#2563ff]"
              >
                Open Reset Page
              </button>
            </div>
          )}
        </div>
      </div>
    </MobileShell>
  );
}