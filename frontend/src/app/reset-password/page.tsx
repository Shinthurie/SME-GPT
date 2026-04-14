"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [message, setMessage] = useState("Validating reset link...");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setMessage("Invalid or expired reset link.");
    } else {
      setMessage("Please enter your new password.");
    }
  }, [token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!token) {
      setError("Invalid or expired reset link.");
      return;
    }

    if (!password || !confirmPassword) {
      setError("Please fill all fields.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token,
          password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Failed to reset password.");
      }

      setSuccess("Password reset successful. Redirecting to login...");
      setTimeout(() => {
        router.push("/login");
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f7f8fb] px-4 py-8">
        <div className="mx-auto max-w-[520px] rounded-[30px] border border-[#d9dff0] bg-white p-8 shadow-sm">
          <h1 className="text-center text-[28px] font-extrabold text-[#0f172a]">
            Reset Password
          </h1>

          <p className="mt-4 text-center text-[14px] text-[#64748b]">
            {message}
          </p>

          {token && (
            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
              <div>
                <label className="mb-2 block text-[12px] font-semibold text-[#475569]">
                  New Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter new password"
                  className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white px-4 text-[15px] text-slate-900 outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                  required
                />
              </div>

              <div>
                <label className="mb-2 block text-[12px] font-semibold text-[#475569]">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white px-4 text-[15px] text-slate-900 outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                  required
                />
              </div>

              {error && (
                <p className="text-[13px] font-medium text-red-600">{error}</p>
              )}

              {success && (
                <p className="text-[13px] font-medium text-green-600">{success}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex h-12 w-full items-center justify-center rounded-2xl bg-[#07122f] text-[16px] font-bold text-white shadow-[0_10px_25px_rgba(7,18,47,0.22)] transition hover:translate-y-[1px] hover:opacity-95 disabled:opacity-60"
              >
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </form>
          )}
        </div>
      </div>
    </MobileShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="p-6 text-center">Loading...</div>}>
      <ResetPasswordContent />
    </Suspense>
  );
}