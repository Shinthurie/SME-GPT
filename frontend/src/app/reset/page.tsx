"use client";

import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import { clearAllDummyAuth } from "@/lib/auth";

export default function ResetPage() {
  const router = useRouter();

  const handleReset = () => {
    clearAllDummyAuth();
    router.push("/signup");
  };

  return (
    <MobileShell>
      <div className="mx-auto flex min-h-screen w-full max-w-[700px] items-center justify-center px-4 py-8">
        <div className="w-full rounded-[20px] border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-[22px] font-bold text-[#0f172a]">Reset Dummy Auth</h1>
          <p className="mt-3 text-[14px] leading-7 text-[#64748b]">
            This will remove the temporary signup user and login session from the browser.
          </p>

          <button
            onClick={handleReset}
            className="mt-6 h-11 w-full rounded-[16px] bg-red-600 text-[14px] font-semibold text-white"
          >
            Clear Dummy Data
          </button>
        </div>
      </div>
    </MobileShell>
  );
}