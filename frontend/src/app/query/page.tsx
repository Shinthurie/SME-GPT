"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function QueryPage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [companyName, setCompanyName] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
    setCompanyName(localStorage.getItem("query_company_name") || "");
  }, []);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 120), 320)}px`;
  }, [question]);

  const t = ui[lang];

  const handleAsk = async () => {
    setError("");
    if (!companyName.trim()) { setError("Please enter your company name first."); return; }
    if (!question.trim()) { setError("Please enter a question."); return; }

    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    localStorage.setItem("query_company_name", companyName.trim());
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/ask-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ company_name: companyName.trim(), question: question.trim() }),
      });

      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }

      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.message || "Failed to answer query.");

      sessionStorage.setItem("query_result", JSON.stringify(data));
      sessionStorage.removeItem("selected_query_history");
      router.push("/answer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[780px] px-4 py-6 sm:px-6 lg:px-8">

          {/* Top bar */}
          <div className="mb-5 flex items-center justify-between">
            <button
              onClick={() => router.push("/dashboard")}
              className="flex items-center gap-1.5 text-[13px] font-semibold transition hover:opacity-75"
              style={{ color: "var(--brand-mid)" }}
            >
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              Back
            </button>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </div>

          <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)] sm:text-[26px]">
            {t.askQuestion}
          </h1>
          <p className="mt-1.5 text-[13px] leading-6 text-[var(--text-2)]">
            Ask questions using only data from your saved financial documents.
          </p>

          {/* Company context */}
          <div
            className="mt-6 rounded-2xl p-5"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--text-3)]">
              Company Context
            </p>
            <input
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Enter your company name (e.g. AIESEC)"
              className="field-input w-full rounded-xl border px-4 py-3 text-[15px] transition"
            />
            <p className="mt-2 text-[12px] text-[var(--text-3)]">
              Used as context scope when searching your documents.
            </p>
          </div>

          {/* Question input */}
          <div
            className="mt-4 rounded-2xl overflow-hidden"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <textarea
              ref={textareaRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Example: What is the total receivable amount?"
              rows={1}
              className="min-h-[120px] w-full resize-none overflow-y-auto bg-transparent px-5 py-5 text-[17px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]"
            />
            <div
              className="flex items-center justify-between px-5 py-3 text-[12px] text-[var(--text-3)]"
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <span>Source: your saved documents only</span>
              <span>Explainable AI enabled</span>
            </div>
          </div>

          {error && (
            <div
              className="mt-4 rounded-xl px-4 py-3 text-[13px] text-red-600"
              style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)" }}
            >
              {error}
            </div>
          )}

          <button
            onClick={handleAsk}
            disabled={loading}
            className="mt-5 flex h-13 w-full items-center justify-center gap-2 rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
            style={{ background: "var(--brand)" }}
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[20px]">progress_activity</span>
                Analysing…
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[20px]">psychology</span>
                Ask Question
              </>
            )}
          </button>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}
