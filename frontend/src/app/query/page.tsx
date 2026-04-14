"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL ="http://127.0.0.1:8000";
function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function QueryPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [companyName, setCompanyName] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
    const savedCompany = localStorage.getItem("query_company_name") || "";
    setCompanyName(savedCompany);
  }, []);

  const t = ui[lang];

  const handleAsk = async () => {
    setError("");

    if (!companyName.trim()) {
      setError("Please enter your company name first.");
      return;
    }

    if (!question.trim()) {
      setError("Please enter a question.");
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setError("Login token missing. Please log in again.");
      router.push("/login");
      return;
    }

    localStorage.setItem("query_company_name", companyName.trim());
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/ask-query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          company_name: companyName.trim(),
          question: question.trim(),
        }),
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        router.push("/login");
        return;
      }

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || data.explanation || "Failed to answer query.");
      }

      sessionStorage.setItem("query_result", JSON.stringify(data));
      router.push("/answer");
    } catch (err: any) {
      setError(err.message || "Something went wrong while asking the question.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={() => router.back()}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>
            <div className="flex items-center gap-2">
              <LanguageSwitcher />
            </div>
          </div>

          <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
            {t.askQuestion}
          </h1>

          <p className="mt-4 max-w-4xl text-[14px] leading-8 text-[#64748b]">
            Ask questions using only data from your saved financial documents.
          </p>

          <div className="mt-6 rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Company Context
            </p>
            <input
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Enter your company name (example: AIESEC)"
              className="mt-3 w-full rounded-[14px] border border-slate-200 px-4 py-3 text-[15px] text-[#0f172a] outline-none focus:border-[#2563ff]"
            />
            <p className="mt-2 text-[12px] text-[#94a3b8]">
              This company name will be used as the main context before answering your question.
            </p>
          </div>

          <div className="mt-6 rounded-[20px] border border-slate-200 bg-white shadow-sm">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Example: What is the receivable amount we have?"
              rows={8}
              className="w-full resize-none rounded-t-[20px] border-0 bg-transparent px-5 py-5 text-[18px] text-[#0f172a] outline-none"
            />
            <div className="flex items-center justify-between rounded-b-[20px] border-t border-slate-100 px-5 py-3 text-[#94a3b8]">
              <div className="text-[12px]">Source: your saved documents only</div>
              <span className="text-[12px]">Explainable answer enabled</span>
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-[16px] border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-700">
              {error}
            </div>
          )}

          <div className="mt-6">
            <button
              onClick={handleAsk}
              disabled={loading}
              className="w-full rounded-[18px] bg-[#2563ff] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)] disabled:opacity-60"
            >
              {loading ? "Analyzing..." : "Ask Question"}
            </button>
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}