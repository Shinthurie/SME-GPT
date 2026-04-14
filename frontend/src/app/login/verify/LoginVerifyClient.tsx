"use client";

import { use, useEffect, useState } from "react";
import MobileShell from "@/components/layout/MobileShell";

export default function LoginVerifyClient({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const params = use(searchParams);
  const verificationToken = params.token || "";

  const [message, setMessage] = useState("Waiting for email confirmation...");

  useEffect(() => {
    if (!verificationToken) {
      setMessage("Invalid verification link.");
      return;
    }

    const interval = setInterval(async () => {
      try {
        const statusRes = await fetch("/api/auth/verification-status", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ verificationToken }),
        });

        const statusData = await statusRes.json();

        if (statusRes.ok && statusData.approved) {
          setMessage("Verification approved. Completing login...");

          const completeRes = await fetch("/api/auth/complete-login", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ verificationToken }),
          });

          if (completeRes.ok) {
            clearInterval(interval);
            window.location.href = "/dashboard";
          }
        }
      } catch (error) {
        console.error("VERIFY PAGE ERROR:", error);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [verificationToken]);

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f7f8fb] px-4 py-8">
        <div className="mx-auto max-w-[520px] rounded-[30px] border border-[#d9dff0] bg-white p-8 shadow-sm">
          <h1 className="text-center text-[28px] font-extrabold text-[#0f172a]">
            Verify Login
          </h1>

          <p className="mt-4 text-center text-[14px] text-[#64748b]">
            {message}
          </p>

          <p className="mt-6 text-center text-[13px] text-[#2563ff]">
            Please check your email and confirm this login.
          </p>
        </div>
      </div>
    </MobileShell>
  );
}