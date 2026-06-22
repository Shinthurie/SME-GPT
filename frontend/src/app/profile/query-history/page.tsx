"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getStoredToken } from "@/lib/auth";

const BACKEND_URL = "http://127.0.0.1:8000";

type QueryHistoryItem = {
  id: string;
  company_name: string;
  question: string;
  answer: string;
  explanation: string;
  metrics: Record<string, unknown>;
  evidence: unknown[];
  source_file: string;
  created_at: string;
};

function formatDateTime(value: string) {
  if (!value) return "No Date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function QueryHistoryPage() {
  const router = useRouter();
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [clearing, setClearing] = useState(false);

  const loadHistory = useCallback(async () => {
    const token = getStoredToken();

    if (!token) {
      router.push("/login");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const res = await fetch(`${BACKEND_URL}/query-history`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to load query history.");
      }

      setHistory(data.history || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const openHistoryItem = (item: QueryHistoryItem) => {
    const payload = {
      success: true,
      company_name: item.company_name,
      question: item.question,
      answer: item.answer,
      explanation: item.explanation,
      evidence: item.evidence || [],
      metrics: item.metrics || {},
      source_file: item.source_file || "",
      opened_from_history: true,
    };

    sessionStorage.setItem("query_result", JSON.stringify(payload));
    sessionStorage.setItem("selected_query_history", JSON.stringify(item));

    router.push("/answer");
  };

  const handleDeleteOne = async (id: string) => {
    const confirmed = window.confirm("Delete this history item?");
    if (!confirmed) return;

    try {
      setDeletingId(id);

      const token = getStoredToken();

      const res = await fetch(`${BACKEND_URL}/query-history/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to delete history item.");
      }

      setHistory((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete history item.");
    } finally {
      setDeletingId("");
    }
  };

  const handleClearAll = async () => {
    const confirmed = window.confirm("Clear all query history?");
    if (!confirmed) return;

    try {
      setClearing(true);

      const token = getStoredToken();

      const res = await fetch(`${BACKEND_URL}/query-history`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to clear history.");
      }

      setHistory([]);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to clear history.");
    } finally {
      setClearing(false);
    }
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <button
              onClick={() => router.push("/profile")}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>

            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <button
                onClick={handleClearAll}
                disabled={clearing || history.length === 0}
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-[13px] font-bold text-red-600 disabled:opacity-50"
              >
                {clearing ? "Clearing..." : "Clear All"}
              </button>
            </div>
          </div>

          <h1 className="text-[24px] font-extrabold text-[#0f172a]">
            Query History
          </h1>

          <p className="mt-2 text-[14px] text-[#64748b]">
            Open, review, or delete your previous saved query answers.
          </p>

          {loading ? (
            <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 text-[14px] text-[#64748b] shadow-sm">
              Loading history...
            </div>
          ) : error ? (
            <div className="mt-6 rounded-[18px] border border-red-200 bg-red-50 p-5 text-[14px] text-red-700 shadow-sm">
              {error}
            </div>
          ) : history.length === 0 ? (
            <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 text-[14px] text-[#64748b] shadow-sm">
              No query history found.
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                        {item.company_name}
                      </p>

                      <h2 className="mt-2 text-[16px] font-bold text-[#0f172a]">
                        {item.question}
                      </h2>

                      <p className="mt-2 line-clamp-2 text-[13px] text-[#64748b]">
                        {item.answer}
                      </p>

                      <p className="mt-3 text-[12px] text-[#94a3b8]">
                        {formatDateTime(item.created_at)}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openHistoryItem(item)}
                        className="rounded-xl bg-[#2563ff] px-4 py-2 text-[13px] font-bold text-white"
                      >
                        Open
                      </button>

                      <button
                        onClick={() => handleDeleteOne(item.id)}
                        disabled={deletingId === item.id}
                        className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-[13px] font-bold text-red-600 disabled:opacity-50"
                      >
                        {deletingId === item.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}