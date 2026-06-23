"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import DerivationTrace from "@/components/ui/DerivationTrace";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

type EvidenceItem = {
  document_id: string;
  document_type: string;
  date: string;
  company_name: string;
  supplier_name: string;
  order_id: string;
  flow_type: string;
  received_status: string;
  paid_status: string;
  currency?: string;
  final_total_amount: number;
  payable_amount: number;
  amount_used?: number;
  reason_used: string;
  items?: {
  description: string;
  quantity: number | string | null;
  unit_price: number | string | null;
  line_total: number | string | null;
}[];
};

type DiscrepancyItem = {
  description: string;
  invoice_price: number;
  po_price: number;
  diff_pct: number;
  is_discrepancy: boolean;
  direction: "higher" | "lower";
};

type QueryResult = {
  success: boolean;
  company_name: string;
  question: string;
  answer: string;
  explanation: string;
  evidence: EvidenceItem[];
  metrics: Record<string, unknown>;
  source_file: string;
  history_saved?: boolean;
  history_error?: string;
  opened_from_history?: boolean;
  discrepancies?: DiscrepancyItem[];
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "NULL";
  return String(value);
}

export default function AnswerPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [followUpQuestion, setFollowUpQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [followUpError, setFollowUpError] = useState("");
  const [showExplanation, setShowExplanation] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [flagged, setFlagged] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const t = ui[lang];

  useEffect(() => {
    setLang(getStoredLanguage());

    const raw = sessionStorage.getItem("query_result");
    if (!raw) {
      setResult(null);
      return;
    }

    try {
      setResult(JSON.parse(raw));
    } catch {
      setResult(null);
    }
  }, []);

  const filteredMetrics = useMemo(() => {
    const metrics = result?.metrics || {};
    const hiddenKeys = new Set(["user_id"]);
    return Object.entries(metrics).filter(([key]) => !hiddenKeys.has(key));
  }, [result]);

  const handleFollowUp = async () => {
    try {
      setFollowUpError("");
      setAsking(true);

      if (!followUpQuestion.trim()) {
        setFollowUpError("Please enter another question.");
        return;
      }

      const token = getAuthToken();
      if (!token) {
        setFollowUpError("Login token missing. Please log in again.");
        router.push("/login");
        return;
      }

      const res = await fetch(`${BACKEND_URL}/ask-query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          company_name: result?.company_name || "",
          question: followUpQuestion.trim(),
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
        throw new Error(data.message || "Failed to answer follow-up question.");
      }

      sessionStorage.setItem("query_result", JSON.stringify(data));
      sessionStorage.removeItem("selected_query_history");

      setResult(data);
      setFollowUpQuestion("");
      setShowExplanation(false);
      setShowEvidence(false);
    } catch (err) {
      setFollowUpError(
        err instanceof Error ? err.message : "Failed to ask follow-up question."
      );
    } finally {
      setAsking(false);
    }
  };

  const handleStartNewChat = () => {
    sessionStorage.removeItem("query_result");
    sessionStorage.removeItem("selected_query_history");
    router.push("/query");
  };

  const handleBack = () => {
    if (result?.opened_from_history) {
      router.push("/profile/query-history");
      return;
    }
    router.push("/query");
  };

  if (!result) {
    return (
      <MobileShell>
        <div className="min-h-screen bg-[#f6f7fb] pb-24">
          <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push("/query")}
                className="text-[14px] font-medium text-[#2563ff]"
              >
                ← Back
              </button>
              <button
                onClick={handleStartNewChat}
                className="rounded-xl bg-[#2563ff] px-4 py-2 text-[13px] font-bold text-white"
              >
                Start New Chat
              </button>
            </div>

            <div className="mt-8 rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b] shadow-sm">
              No query result found.
            </div>
          </main>
          <BottomNav />
        </div>
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <button
              onClick={handleBack}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>

            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <button
                onClick={handleStartNewChat}
                className="rounded-xl bg-[#2563ff] px-4 py-2 text-[13px] font-bold text-white"
              >
                Start New Chat
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                Insights &amp; Analysis
              </p>
              <h1 className="text-[24px] font-extrabold text-[#0f172a]">
                AI Business Insight
              </h1>
            </div>
            <span
              className="rounded-xl px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider"
              style={{ background: "rgba(34,82,181,0.08)", color: "#2252b5" }}
            >
              98% Accuracy
            </span>
          </div>

          {result.history_saved === false && (
            <div className="mt-4 rounded-[16px] border border-amber-200 bg-amber-50 px-4 py-3 text-[14px] text-amber-700">
              Query answered, but history was not saved to DB.
              {result.history_error ? ` (${result.history_error})` : ""}
            </div>
          )}

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Company Context
            </p>
            <p className="mt-3 text-[14px] font-semibold text-[#0f172a]">
              {result.company_name}
            </p>
          </div>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Question
            </p>
            <p className="mt-2 text-[14px] text-[#0f172a]">{result.question}</p>
          </div>

          <div className="mt-6 rounded-[18px] border border-[#c8d7ff] bg-[#eef4ff] p-5">
            <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#2563ff]">
              Answer
            </p>
            <p className="mt-3 whitespace-pre-line text-[16px] font-semibold leading-7 text-[#0f172a]">
  {result.answer}
</p>
          </div>

          {/* Action buttons — UI Design 6 */}
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <button
              onClick={() => {
                const firstDoc = result.evidence?.[0];
                if (firstDoc) router.push(`/analysis/${firstDoc.document_id}`);
              }}
              className="flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[12px] font-bold transition hover:opacity-80"
              style={{ background: "rgba(34,82,181,0.08)", color: "#2252b5", border: "1px solid rgba(34,82,181,0.18)" }}
            >
              <span className="material-symbols-outlined text-[15px]">edit_note</span>
              Adjust Total
            </button>
            <button
              onClick={() => setNotifyOpen((p) => !p)}
              className="flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[12px] font-bold transition hover:opacity-80"
              style={{ background: "rgba(34,82,181,0.08)", color: "#2252b5", border: "1px solid rgba(34,82,181,0.18)" }}
            >
              <span className="material-symbols-outlined text-[15px]">mail</span>
              Notify Supplier
            </button>
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `query-result-${Date.now()}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[12px] font-bold transition hover:opacity-80"
              style={{ background: "rgba(22,163,74,0.08)", color: "#16a34a", border: "1px solid rgba(22,163,74,0.18)" }}
            >
              <span className="material-symbols-outlined text-[15px]">download</span>
              Export
            </button>
            <button
              onClick={() => setFlagged((p) => !p)}
              className="flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[12px] font-bold transition hover:opacity-80"
              style={
                flagged
                  ? { background: "rgba(220,38,38,0.1)", color: "#dc2626", border: "1px solid rgba(220,38,38,0.2)" }
                  : { background: "#0f172a", color: "#fff" }
              }
            >
              <span className="material-symbols-outlined text-[15px]">flag</span>
              {flagged ? "Flagged ✓" : "Flag for Review"}
            </button>
          </div>

          {notifyOpen && (
            <div className="mt-3 rounded-[14px] border border-slate-200 bg-white p-4 text-[13px] text-[#334155]">
              <p className="font-semibold text-[#0f172a]">Notify Supplier</p>
              <p className="mt-1 text-[#64748b]">
                Compose a message to the supplier regarding discrepancies or payment status. (Email integration coming soon.)
              </p>
              <button onClick={() => setNotifyOpen(false)} className="mt-2 text-[12px] font-bold text-[#2563ff]">
                Dismiss
              </button>
            </div>
          )}

          {/* GAP-19B: Price discrepancy card (Iter 19 — SRS UI-D6 use case) */}
          {result.discrepancies && result.discrepancies.length > 0 && (
            <div className="mt-4 rounded-[18px] border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-amber-600">warning</span>
                <p className="text-[13px] font-bold text-amber-800 uppercase tracking-wide">
                  Price Discrepancy Found
                </p>
              </div>
              <div className="mt-3 space-y-3">
                {result.discrepancies.filter(d => d.is_discrepancy).map((d, i) => (
                  <div key={i} className="rounded-[12px] border border-amber-200 bg-white px-4 py-3">
                    <p className="text-[13px] font-semibold text-[#0f172a]">{d.description}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-[12px]">
                      <span className="text-[#334155]">
                        Invoice: <span className="font-bold text-red-600">{d.invoice_price.toLocaleString()}</span>
                      </span>
                      <span className="text-[#334155]">
                        PO: <span className="font-bold text-[#16a34a]">{d.po_price.toLocaleString()}</span>
                      </span>
                      <span
                        className="rounded-lg px-2 py-0.5 text-[11px] font-bold"
                        style={{
                          background: d.direction === "higher" ? "rgba(220,38,38,0.1)" : "rgba(22,163,74,0.1)",
                          color: d.direction === "higher" ? "#dc2626" : "#16a34a",
                        }}
                      >
                        {d.diff_pct > 0 ? "+" : ""}{d.diff_pct}% {d.direction.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white shadow-sm">
            <button
              onClick={() => setShowExplanation((prev) => !prev)}
              className="flex w-full items-center justify-between px-5 py-4 text-left"
            >
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                Explanation
              </span>
              <span className="material-symbols-outlined text-[#64748b]">
                {showExplanation ? "expand_less" : "expand_more"}
              </span>
            </button>

            {showExplanation && (
  <div className="border-t border-slate-100 px-5 py-4 text-[14px] leading-7 text-[#334155]">
    <p>{result.explanation}</p>

    <div className="mt-4 rounded-[12px] bg-[#f8fafc] px-4 py-3">
      <p className="text-[12px] font-semibold text-[#475569]">
        Source used: <span className="font-bold">{result.source_file}</span>
      </p>
    </div>

    <div className="mt-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
        Metrics
      </p>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {filteredMetrics.length === 0 ? (
          <div className="text-[14px] text-[#64748b]">No metrics available.</div>
        ) : (
          filteredMetrics.map(([key, value]) => (
            <div
              key={key}
              className="rounded-[14px] border border-slate-200 px-4 py-3"
            >
              <p className="text-[11px] text-[#94a3b8]">{key}</p>
              <p className="mt-1 text-[15px] font-semibold text-[#0f172a]">
                {formatValue(value)}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  </div>
)}
          </div>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white shadow-sm">
            <button
              onClick={() => setShowEvidence((prev) => !prev)}
              className="flex w-full items-center justify-between px-5 py-4 text-left"
            >
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                Evidence Documents
              </span>
              <span className="material-symbols-outlined text-[#64748b]">
                {showEvidence ? "expand_less" : "expand_more"}
              </span>
            </button>

            {showEvidence && (
              <div className="border-t border-slate-100 px-5 py-4">
                <div className="space-y-4">
                  {result.evidence && result.evidence.length > 0 ? (
                    result.evidence.map((item, index) => (
                      <div
                        key={`${item.document_id}-${index}`}
                        className="rounded-[14px] border border-slate-200 p-4"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p className="text-[15px] font-bold text-[#0f172a]">
                            {item.document_id}
                          </p>
                          <div className="flex items-center gap-2">
                            <span className="rounded-xl bg-[#eef4ff] px-3 py-1.5 text-[11px] font-semibold text-[#2563ff]">
                              {item.document_type?.toUpperCase()}
                            </span>
                            {item.document_type === "po" && (
                              <button
                                onClick={() => router.push(`/analysis/${item.document_id}`)}
                                className="rounded-xl border border-[#2252b5] px-3 py-1 text-[11px] font-bold text-[#2252b5] hover:bg-[#eef4ff] transition"
                              >
                                GO TO PO →
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Date:</span> {item.date}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Order ID:</span> {item.order_id}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Company:</span> {item.company_name}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Supplier:</span> {item.supplier_name}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Flow Type:</span> {item.flow_type}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Currency:</span> {formatValue(item.currency)}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Final Total:</span> {formatValue(item.final_total_amount)}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Payable Amount:</span> {formatValue(item.payable_amount)}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Amount Used:</span> {formatValue(item.amount_used ?? item.final_total_amount)}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Received Status:</span> {item.received_status}</p>
                          <p className="text-[13px] text-[#334155]"><span className="font-semibold">Paid Status:</span> {item.paid_status}</p>
                        </div>

                        <div className="mt-3 rounded-[12px] bg-[#f8fafc] px-3 py-3 text-[12px] text-[#475569]">
                          <span className="font-semibold">Reason used:</span> {item.reason_used}
                        </div>
                        {item.items && item.items.length > 0 && (
  <div className="mt-3 rounded-[12px] border border-slate-100 bg-white px-3 py-3">
    <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
      Items
    </p>

    <div className="mt-2 space-y-2">
      {item.items.map((it, idx) => (
        <div
          key={idx}
          className="rounded-[10px] bg-[#f8fafc] px-3 py-2 text-[12px] text-[#334155]"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold">{formatValue(it.description)}</p>
            <span className="shrink-0 rounded-md bg-slate-200 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">
              ROW {idx + 1}
            </span>
          </div>
          <p className="mt-0.5">
            Qty: {formatValue(it.quantity)} · Unit Price: {formatValue(it.unit_price)} · Line Total: {formatValue(it.line_total)}
          </p>
        </div>
      ))}
    </div>
  </div>
)}
                      </div>
                    ))
                  ) : (
                    <div className="text-[14px] text-[#64748b]">No evidence documents available.</div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Derivation Trace — Iteration 7 */}
          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white shadow-sm">
            <button
              onClick={() => setShowTrace((prev) => !prev)}
              className="flex w-full items-center justify-between px-5 py-4 text-left"
            >
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                {t.derivationTrace ?? "Derivation Trace"}
              </span>
              <span className="material-symbols-outlined text-[#64748b]">
                {showTrace ? "expand_less" : "expand_more"}
              </span>
            </button>
            {showTrace && (
              <div className="border-t border-slate-100 px-5 py-4">
                <DerivationTrace
                  evidence={result.evidence || []}
                  metrics={result.metrics || {}}
                  questionType={
                    (result.metrics?.question_type as string) || "summary"
                  }
                  companyName={result.company_name}
                />
              </div>
            )}
          </div>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Ask a Follow-up
            </p>

            <textarea
              value={followUpQuestion}
              onChange={(e) => setFollowUpQuestion(e.target.value)}
              placeholder="Ask another question from the same company context..."
              rows={4}
              className="mt-4 w-full rounded-[14px] border border-slate-200 px-4 py-3 text-[15px] text-[#0f172a] outline-none focus:border-[#2563ff]"
            />

            {followUpError && (
              <div className="mt-4 rounded-[14px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                {followUpError}
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={handleFollowUp}
                disabled={asking}
                className="rounded-xl bg-[#2563ff] px-4 py-2 text-[13px] font-bold text-white disabled:opacity-60"
              >
                {asking ? "Analyzing..." : "Ask Follow-up"}
              </button>

              <button
                onClick={handleStartNewChat}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-bold text-[#64748b]"
              >
                Start New Chat
              </button>
            </div>
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}