"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/layout/PageShell";
import { AppLanguage, getStoredLanguage, setStoredLanguage, ui } from "@/lib/i18n";
import { getSession } from "@/lib/auth";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function QueryPage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [companyName, setCompanyName] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [attachedFile, setAttachedFile] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    setLang(getStoredLanguage());
    // Auto-populate company name from user profile session
    getSession().then(s => {
      if (s?.companyName) {
        setCompanyName(s.companyName);
      } else {
        // Fall back to last-used value if session has no company
        setCompanyName(localStorage.getItem("query_company_name") || "");
      }
    });
  }, []);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 120), 320)}px`;
  }, [question]);

  const t = ui[lang];

  const handleVoice = () => {
    type SR = { new(): {
      lang: string; interimResults: boolean; continuous: boolean;
      onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null;
      onend: (() => void) | null;
      onerror: (() => void) | null;
      start: () => void;
    }};
    const w = window as unknown as Record<string, unknown>;
    const SRClass = (w.SpeechRecognition || w.webkitSpeechRecognition) as SR | undefined;
    if (!SRClass) { setError("Voice input is not supported in this browser. Use Chrome or Edge."); return; }
    const recognition = new SRClass();
    recognition.lang = lang === "si" ? "si-LK" : "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    setIsListening(true);
    recognition.onresult = (e) => {
      const transcript = Array.from({ length: (e.results as unknown as ArrayLike<unknown>).length },
        (_, i) => (e.results[i][0] as {transcript: string}).transcript).join("");
      setQuestion(transcript);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => { setIsListening(false); setError("Voice input failed. Please try again."); };
    recognition.start();
  };

  const handleLangToggle = () => {
    const next: AppLanguage = lang === "en" ? "si" : "en";
    setLang(next);
    setStoredLanguage(next);
    try {
      window.dispatchEvent(new CustomEvent("app-language-changed", { detail: next }));
    } catch {}
    setTimeout(() => { try { window.location.reload(); } catch {} }, 50);
  };

  const handleAttach = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAttachedFile(file.name);
    // Append file context to question
    setQuestion(prev => prev ? `${prev}\n[Attached document: ${file.name}]` : `[Attached document: ${file.name}]`);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleAsk = async () => {
    setError("");
    if (!companyName.trim()) { setError("Company name not found. Please update your profile with your company name."); return; }
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
    <PageShell
      backLabel={t.backToDashboard}
      backHref="/dashboard"
      title={t.askQuestion}
      subtitle="Ask questions about your invoices, delivery notes, or purchase orders in English or Sinhala."
      width="standard"
      topBarRight={
        <div className="flex items-center gap-2">
          <span className="rounded-lg px-3 py-1 text-[10px] font-bold uppercase tracking-wider"
            style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
            Document AI
          </span>
        </div>
      }
    >

          {/* Company context */}
          {/* Company context — auto-filled from user profile, read-only */}
          <div
            className="mt-6 flex items-center gap-3 rounded-2xl px-5 py-4"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <span className="material-symbols-outlined text-[20px]" style={{ color: "var(--brand-mid)" }}>
              domain
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
                {lang === "si" ? "සමාගම" : "Company"}
              </p>
              <p className="mt-0.5 truncate text-[15px] font-semibold text-[var(--text-1)]">
                {companyName || (lang === "si" ? "පූරණය වෙමින්…" : "Loading…")}
              </p>
            </div>
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
              className="flex items-center justify-between px-5 py-3"
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <div className="flex items-center gap-4">
                <button
                  onClick={handleVoice}
                  title={isListening ? "Listening… speak now" : "Voice input"}
                  className="transition hover:opacity-70"
                  style={{ color: isListening ? "#dc2626" : "var(--text-3)" }}
                >
                  <span className="material-symbols-outlined text-[20px]">
                    {isListening ? "stop_circle" : "mic"}
                  </span>
                </button>
                <button
                  onClick={handleLangToggle}
                  title={`Language: ${lang === "si" ? "Sinhala" : "English"} — click to toggle`}
                  className="transition hover:opacity-70"
                  style={{ color: "var(--brand-mid)" }}
                >
                  <span className="material-symbols-outlined text-[20px]">g_translate</span>
                </button>
              </div>
              <span className="text-[11px] text-[var(--text-3)]">
                {lang === "si" ? "සිංහල" : "English"}
              </span>
            </div>
          </div>

          {isListening && (
            <div className="mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-[12px] text-red-600"
              style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
              <span className="material-symbols-outlined text-[14px] animate-pulse">mic</span>
              Listening… speak your question now
            </div>
          )}

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
                <span className="material-symbols-outlined text-[20px]">search</span>
                Ask Question
              </>
            )}
          </button>
          {/* OCR / NLP / XAI pipeline indicator */}
          <div className="mt-6 flex items-center justify-center gap-6">
            {[
              { icon: "document_scanner", label: "OCR" },
              { icon: "chat",             label: "NLP" },
              { icon: "lightbulb",        label: "XAI" },
            ].map(({ icon, label }) => (
              <div key={label} className="flex flex-col items-center gap-1">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--brand-mid)" }}>
                    {icon}
                  </span>
                </div>
                <span className="text-[10px] font-bold text-[var(--text-3)]">{label}</span>
              </div>
            ))}
          </div>
    </PageShell>
  );
}
