"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import ThemeToggle from "@/components/layout/ThemeToggle";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { getSession } from "@/lib/auth";
import { formatMoney, otherPartyName } from "@/lib/format";
import { humanizeFlow } from "@/lib/humanize";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

const THREAD_KEY = "agent_chat_thread_id";
const MESSAGES_KEY = "agent_chat_messages";

type ChatEvidenceItem = {
  document_id: string;
  document_type: string;
  date: string;
  supplier_name: string;
  flow_type: string;
  flow_direction?: "income" | "expense";
  currency?: string;
  amount_used?: number;
  final_total_amount: number;
  po_status?: string | null;
  dn_status?: string | null;
  invoice_status?: string | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  evidence?: ChatEvidenceItem[];
  isError?: boolean;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function AiAssistantChatPage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const [lang, setLang] = useState<AppLanguage>("en");
  const [companyName, setCompanyName] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);

  const t = ui[lang];

  useEffect(() => {
    setLang(getStoredLanguage());
    getSession().then((s) => {
      if (s?.companyName) setCompanyName(s.companyName);
    });

    try {
      const storedThread = sessionStorage.getItem(THREAD_KEY);
      const storedMessages = sessionStorage.getItem(MESSAGES_KEY);
      if (storedThread) setThreadId(storedThread);
      if (storedMessages) setMessages(JSON.parse(storedMessages));
    } catch {
      // ignore corrupt sessionStorage
    }
    setHydrated(true);
  }, []);

  // Persist conversation so a refresh doesn't lose it.
  useEffect(() => {
    if (!hydrated) return;
    try {
      sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(messages));
      if (threadId) sessionStorage.setItem(THREAD_KEY, threadId);
      else sessionStorage.removeItem(THREAD_KEY);
    } catch {
      // ignore quota errors
    }
  }, [messages, threadId, hydrated]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 44), 160)}px`;
  }, [input]);

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
      setInput(transcript);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => { setIsListening(false); setError("Voice input failed. Please try again."); };
    recognition.start();
  };

  const handleNewChat = () => {
    setMessages([]);
    setThreadId(null);
    setError("");
    try {
      sessionStorage.removeItem(MESSAGES_KEY);
      sessionStorage.removeItem(THREAD_KEY);
    } catch {}
  };

  const toggleEvidence = (id: string) => {
    setExpandedEvidence((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;
    setError("");

    if (!companyName.trim()) {
      setError("Company name not found. Please update your profile with your company name.");
      return;
    }

    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    const userMsg: ChatMessage = { id: newId(), role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          company_name: companyName.trim(),
          question,
          thread_id: threadId ?? undefined,
        }),
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        router.push("/login");
        return;
      }

      if (res.status === 503) {
        setMessages((prev) => [
          ...prev,
          { id: newId(), role: "assistant", content: t.aiAssistantDisabled, isError: true },
        ]);
        return;
      }

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.message || t.aiAssistantSendError);
      }

      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", content: data.answer, evidence: data.evidence || [] },
      ]);
      if (data.thread_id) setThreadId(data.thread_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : t.aiAssistantSendError;
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", content: msg, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <MobileShell hideQuickActions>
      <div className="flex h-screen flex-col" style={{ background: "var(--bg)" }}>
        {/* Header */}
        <div
          className="shrink-0 px-4 py-3 sm:px-6"
          style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}
        >
          <div className="mx-auto flex w-full max-w-[960px] items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <button
                onClick={() => router.push("/query")}
                className="flex items-center gap-1 text-[13px] font-semibold transition hover:opacity-75"
                style={{ color: "var(--brand-mid)" }}
              >
                <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              </button>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="truncate text-[16px] font-extrabold text-[var(--text-1)]">
                    {t.aiAssistant}
                  </h1>
                  <span
                    className="rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                    style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
                  >
                    {t.aiAssistantBeta}
                  </span>
                </div>
                <p className="truncate text-[11px] text-[var(--text-3)]">{companyName || "…"}</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleNewChat}
                title={t.aiAssistantNewChat}
                className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold transition hover:opacity-80"
                style={{ background: "var(--surface-2)", color: "var(--text-2)" }}
              >
                <span className="material-symbols-outlined text-[16px]">add_comment</span>
                <span className="hidden sm:inline">{t.aiAssistantNewChat}</span>
              </button>
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6" style={{ paddingBottom: "160px" }}>
          <div className="mx-auto w-full max-w-[960px] space-y-4">
            {messages.length === 0 && (
              <div
                className="rounded-2xl px-5 py-4 text-[14px] leading-6"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}
              >
                {t.aiAssistantGreeting}
              </div>
            )}

            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] ${m.role === "user" ? "" : "w-full"}`}>
                  <div
                    className="whitespace-pre-line rounded-2xl px-4 py-3 text-[14px] leading-6"
                    style={
                      m.role === "user"
                        ? { background: "var(--brand)", color: "#fff" }
                        : m.isError
                        ? { background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)", color: "#dc2626" }
                        : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-1)" }
                    }
                  >
                    {m.content}
                  </div>

                  {m.role === "assistant" && m.evidence && m.evidence.length > 0 && (
                    <div className="mt-1.5">
                      <button
                        onClick={() => toggleEvidence(m.id)}
                        className="flex items-center gap-1 text-[11px] font-semibold transition hover:opacity-75"
                        style={{ color: "var(--brand-mid)" }}
                      >
                        <span className="material-symbols-outlined text-[14px]">
                          {expandedEvidence.has(m.id) ? "expand_less" : "expand_more"}
                        </span>
                        {t.aiAssistantSources} ({m.evidence.length})
                      </button>

                      {expandedEvidence.has(m.id) && (
                        <div className="mt-2 space-y-2">
                          {m.evidence.map((item, idx) => (
                            <div
                              key={`${item.document_id}-${idx}`}
                              className="rounded-xl px-3 py-2.5 text-[12px]"
                              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-bold text-[var(--text-1)]">
                                  {otherPartyName(item) || item.document_id}
                                </span>
                                <span
                                  className="rounded-md px-2 py-0.5 text-[10px] font-bold uppercase"
                                  style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
                                >
                                  {item.document_type}
                                </span>
                              </div>
                              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[var(--text-3)]">
                                <span>{item.document_id}</span>
                                <span>{item.date}</span>
                                <span>{humanizeFlow(item.flow_type, lang)}</span>
                                <span className="font-semibold text-[var(--text-2)]">
                                  {formatMoney(item.amount_used ?? item.final_total_amount, item.currency) || "—"}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div
                  className="flex items-center gap-2 rounded-2xl px-4 py-3 text-[13px]"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-3)" }}
                >
                  <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
                  {t.aiAssistantSending}
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input bar — fixed above BottomNav */}
        <div
          className="fixed bottom-[64px] left-0 right-0 z-40 px-4 py-3 sm:px-6"
          style={{ background: "var(--surface)", borderTop: "1px solid var(--border)" }}
        >
          <div className="mx-auto w-full max-w-[960px]">
            {error && (
              <div
                className="mb-2 rounded-xl px-3 py-2 text-[12px] text-red-600"
                style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)" }}
              >
                {error}
              </div>
            )}
            {isListening && (
              <div className="mb-2 flex items-center gap-2 text-[12px] text-red-600">
                <span className="material-symbols-outlined text-[14px] animate-pulse">mic</span>
                {t.listeningMsg}
              </div>
            )}
            <div
              className="flex items-end gap-2 rounded-2xl px-2 py-2"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
            >
              <button
                onClick={handleVoice}
                title={t.voiceInput}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition hover:opacity-70"
                style={{ color: isListening ? "#dc2626" : "var(--text-3)" }}
              >
                <span className="material-symbols-outlined text-[19px]">
                  {isListening ? "stop_circle" : "mic"}
                </span>
              </button>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t.aiAssistantPlaceholder}
                rows={1}
                className="min-h-[36px] flex-1 resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-[14px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]"
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                title={t.aiAssistantSend}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white transition hover:opacity-90 disabled:opacity-40"
                style={{ background: "var(--brand)" }}
              >
                <span className="material-symbols-outlined text-[19px]">send</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <BottomNav />
    </MobileShell>
  );
}
