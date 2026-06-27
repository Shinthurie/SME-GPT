"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

type RepoDocument = {
  document_id: string;
  document_type: "invoice" | "po" | "dn" | "receipt" | "unknown";
  company_name: string;
  supplier_name: string;
  date: string;
  raw_total_amount?: string | number;
  final_total_amount?: string | number;
  payable_amount?: string | number;
  currency: string;
  status: string;
  flow_type?: string;
  file_size_kb?: number | null;
  // Iteration 10: workflow status fields
  po_status?: string | null;
  dn_status?: string | null;
  invoice_status?: string | null;
};

type TabType = "all" | "invoice" | "po" | "dn" | "receipt" | "archived";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function isUsable(v: unknown) {
  if (v === undefined || v === null) return false;
  const t = String(v).trim();
  return t !== "" && t.toUpperCase() !== "NULL";
}

const typeMap: Record<RepoDocument["document_type"], { bg: string; color: string; icon: string; label: string }> = {
  invoice: { bg: "rgba(34,82,181,0.1)", color: "#2252b5", icon: "description", label: "INVOICE" },
  po:      { bg: "rgba(124,58,237,0.1)", color: "#7c3aed", icon: "shopping_cart", label: "PURCHASE ORDER" },
  dn:      { bg: "rgba(249,115,22,0.1)", color: "#ea6c0a", icon: "local_shipping", label: "DELIVERY NOTE" },
  receipt: { bg: "rgba(22,163,74,0.1)",  color: "#16a34a", icon: "receipt_long", label: "RECEIPT" },
  unknown: { bg: "rgba(100,116,139,0.1)", color: "#64748b", icon: "draft", label: "DOCUMENT" },
};

function statusBadge(status: string) {
  const s = (status || "ready").toLowerCase();
  if (s === "processing")
    return { bg: "rgba(234,108,10,0.1)", color: "#ea6c0a", label: "PROCESSING" };
  if (s === "error" || s === "failed")
    return { bg: "rgba(220,38,38,0.1)", color: "#dc2626", label: "ERROR" };
  return { bg: "rgba(22,163,74,0.1)", color: "#16a34a", label: "READY" };
}

function formatFileSize(kb?: number | null) {
  if (kb == null || isNaN(Number(kb)) || Number(kb) <= 0) return null;
  const n = Number(kb);
  if (n >= 1024) return `${(n / 1024).toFixed(1)} MB`;
  return `${Math.round(n)} KB`;
}

export default function RepositoryPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [tab, setTab] = useState<TabType>("all");
  const [documents, setDocuments] = useState<RepoDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  // IT-21: server-side upload-date range filter
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [autoClassify, setAutoClassify] = useState(true);
  // Iteration 10: per-tab status filters
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    setLang(getStoredLanguage());
    // Fetch the user's autoClassify setting to control which tabs are shown
    fetch("/api/profile")
      .then(r => r.json())
      .then(d => {
        if (typeof d?.user?.autoClassify === "boolean") {
          setAutoClassify(d.user.autoClassify);
          if (!d.user.autoClassify) setTab("all");
        }
      })
      .catch(() => {});
  }, []);

  const t = ui[lang];

  const loadDocuments = async () => {
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (dateFrom) params.set("from", dateFrom);
      if (dateTo) params.set("to", dateTo);
      const res = await fetch(`${BACKEND_URL}/documents?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.message || "Failed to fetch.");
      setDocuments(data.documents || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch documents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDocuments(); }, [router, dateFrom, dateTo]);

  // Reset statusFilter when the main tab changes
  const handleTabChange = (v: TabType) => { setTab(v); setStatusFilter("all"); };

  const filtered = useMemo(() => {
    let byTab: RepoDocument[];
    if (tab === "archived") {
      byTab = documents.filter((d) => String(d.status).toLowerCase() === "archived");
    } else if (tab === "all") {
      byTab = documents.filter((d) => String(d.status).toLowerCase() !== "archived");
    } else {
      byTab = documents.filter((d) => d.document_type === tab && String(d.status).toLowerCase() !== "archived");
    }
    // Iteration 10: apply workflow status sub-filter
    if (statusFilter !== "all") {
      byTab = byTab.filter((d) => {
        if (tab === "po")      return (d.po_status      || "pending").toLowerCase() === statusFilter;
        if (tab === "invoice") return (d.invoice_status || "pending").toLowerCase() === statusFilter;
        if (tab === "dn")      return (d.dn_status      || "pending").toLowerCase() === statusFilter;
        return true;
      });
    }
    if (!searchQuery.trim()) return byTab;
    const q = searchQuery.toLowerCase();
    return byTab.filter(
      (d) =>
        d.document_id.toLowerCase().includes(q) ||
        (d.company_name || "").toLowerCase().includes(q) ||
        (d.supplier_name || "").toLowerCase().includes(q)
    );
  }, [tab, documents, searchQuery, statusFilter]);

  const tabLabel = (v: TabType) => {
    const labels: Record<TabType, string> = {
      all: t.documentsAll, invoice: lang === "si" ? "ඉන්වොයිස්" : "Invoice",
      po: "PO", dn: "DN", receipt: lang === "si" ? "රිසිට්" : "Receipt",
      archived: lang === "si" ? "සංරක්ෂිත" : "Archived",
    };
    return labels[v];
  };

  const formatAmount = (item: RepoDocument) => {
    const amt = isUsable(item.payable_amount)
      ? item.payable_amount
      : isUsable(item.final_total_amount)
      ? item.final_total_amount
      : isUsable(item.raw_total_amount)
      ? item.raw_total_amount
      : null;
    if (!amt) return t.noAmount;
    const cur = item.currency && item.currency !== "NULL" ? item.currency : "LKR";
    return `${cur} ${amt}`;
  };

  const partyName = (item: RepoDocument) => {
    if (item.company_name && item.company_name !== "NULL") return item.company_name;
    if (item.supplier_name && item.supplier_name !== "NULL") return item.supplier_name;
    return "Unknown Party";
  };

  const partyLabel = (item: RepoDocument) => {
    if (item.document_type === "po") return "Client";
    if (item.document_type === "dn") return "Receiver";
    const ft = String(item.flow_type || "").toLowerCase();
    if (ft === "receivable") return "Customer";
    return "Vendor";
  };

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[920px] px-4 py-6 sm:px-6 lg:px-8">

          {/* Header */}
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)] sm:text-[26px]">
                {t.repositoryTitle}
              </h1>
              <p className="mt-0.5 text-[12px] text-[var(--text-3)]">
                {t.repoSubtitle}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <LanguageSwitcher />
              <button
                onClick={() => router.push("/upload")}
                className="flex h-9 w-9 items-center justify-center rounded-full text-white shadow-sm transition hover:opacity-90"
                style={{ background: "var(--brand)" }}
              >
                <span className="material-symbols-outlined text-[20px]">add</span>
              </button>
            </div>
          </div>

          {/* Search bar */}
          <div className="mb-4 flex items-center gap-2 rounded-xl px-4 py-2.5"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--text-3)" }}>search</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t.searchPlaceholder}
              className="flex-1 bg-transparent text-[14px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} className="text-[var(--text-3)] hover:text-[var(--text-1)]">
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            )}
          </div>

          {/* IT-21: Upload-date range filter */}
          <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl px-4 py-2.5"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--text-3)" }}>date_range</span>
            <span className="text-[12px] font-semibold text-[var(--text-2)]">
              {lang === "si" ? "උඩුගත කළ දිනය" : "Upload date"}
            </span>
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => setDateFrom(e.target.value)}
              aria-label={lang === "si" ? "සිට" : "From"}
              className="rounded-lg px-2 py-1 text-[13px] text-[var(--text-1)] outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
            />
            <span className="text-[12px] text-[var(--text-3)]">{lang === "si" ? "–" : "to"}</span>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => setDateTo(e.target.value)}
              aria-label={lang === "si" ? "දක්වා" : "To"}
              className="rounded-lg px-2 py-1 text-[13px] text-[var(--text-1)] outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
            />
            {(dateFrom || dateTo) && (
              <button
                onClick={() => { setDateFrom(""); setDateTo(""); }}
                className="ml-auto flex items-center gap-1 text-[12px] font-bold transition hover:opacity-75"
                style={{ color: "var(--text-3)" }}
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
                {lang === "si" ? "හිස් කරන්න" : "Clear"}
              </button>
            )}
          </div>

          {/* Tabs */}
          <div className="mb-5 flex flex-wrap gap-2">
            {(autoClassify
              ? (["all", "invoice", "po", "dn", "receipt", "archived"] as TabType[])
              : (["all", "archived"] as TabType[])
            ).map((v) => (
              <button
                key={v}
                onClick={() => handleTabChange(v)}
                className="rounded-full px-4 py-1.5 text-[12px] font-semibold transition"
                style={
                  tab === v
                    ? { background: "var(--brand)", color: "#fff" }
                    : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }
                }
              >
                {tabLabel(v)}
              </button>
            ))}
          </div>

          {/* Iteration 10: Status sub-filter chips */}
          {tab === "po" && (
            <div className="mb-4 flex flex-wrap gap-2">
              {[
                { v: "all", label: "All" },
                { v: "pending", label: "⏳ Pending" },
                { v: "approved", label: "✅ Approved" },
                { v: "rejected", label: "❌ Rejected" },
                { v: "fulfilled", label: "📦 Fulfilled" },
                { v: "cancelled", label: "🚫 Cancelled" },
                { v: "partially_delivered", label: "⚠ Partial" },
              ].map(({ v, label }) => (
                <button key={v} onClick={() => setStatusFilter(v)}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold transition"
                  style={statusFilter === v
                    ? { background: "#7c3aed", color: "#fff" }
                    : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                  {label}
                </button>
              ))}
            </div>
          )}
          {tab === "invoice" && (
            <div className="mb-4 flex flex-wrap gap-2">
              {[
                { v: "all", label: "All" },
                { v: "pending", label: "⏳ Pending" },
                { v: "overdue", label: "🔴 Overdue" },
                { v: "paid", label: "✅ Paid" },
                { v: "partially_paid", label: "⚠ Partial" },
                { v: "cancelled", label: "🚫 Cancelled" },
              ].map(({ v, label }) => (
                <button key={v} onClick={() => setStatusFilter(v)}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold transition"
                  style={statusFilter === v
                    ? { background: "#2252b5", color: "#fff" }
                    : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                  {label}
                </button>
              ))}
            </div>
          )}
          {tab === "dn" && (
            <div className="mb-4 flex flex-wrap gap-2">
              {[
                { v: "all", label: "All" },
                { v: "pending", label: "⏳ Pending" },
                { v: "delivered", label: "✅ Delivered" },
                { v: "delayed", label: "🔴 Delayed" },
                { v: "partially_delivered", label: "⚠ Partial" },
                { v: "failed", label: "❌ Failed" },
                { v: "returned", label: "↩ Returned" },
              ].map(({ v, label }) => (
                <button key={v} onClick={() => setStatusFilter(v)}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold transition"
                  style={statusFilter === v
                    ? { background: "#ea6c0a", color: "#fff" }
                    : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Content */}
          {loading ? (
            <div className="rounded-2xl px-4 py-8 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {t.loading}
            </div>
          ) : error ? (
            <div className="rounded-2xl px-4 py-6 text-center text-[14px] text-red-600"
              style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
              {error}
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-2xl px-4 py-8 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {t.noDocumentsFound}
            </div>
          ) : (
            <>
            <div className="space-y-3">
              {filtered.map((item) => {
                const m = typeMap[item.document_type] ?? typeMap.unknown;
                const amt = formatAmount(item);
                const badge = statusBadge(item.status);
                const fileSize = formatFileSize(item.file_size_kb);
                return (
                  <div
                    key={item.document_id}
                    className="rounded-2xl p-4"
                    style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl" style={{ background: m.bg }}>
                        <span className="material-symbols-outlined text-[20px]" style={{ color: m.color }}>{m.icon}</span>
                      </div>

                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">{m.label}</p>
                        <p className="mt-0.5 text-[15px] font-bold text-[var(--text-1)]">{item.document_id}</p>

                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <div>
                            <p className="text-[11px] text-[var(--text-3)]">{partyLabel(item)}</p>
                            <p className="text-[13px] text-[var(--text-1)]">{partyName(item)}</p>
                          </div>
                          <div className="sm:text-right">
                            <p className="text-[11px] text-[var(--text-3)]">Date</p>
                            <p className="text-[13px] text-[var(--text-1)]">
                              {item.date && item.date !== "NULL" ? item.date : "No Date"}
                            </p>
                          </div>
                        </div>

                        {fileSize && (
                          <p className="mt-1 text-[11px] text-[var(--text-3)]">{fileSize}</p>
                        )}

                        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                          <span
                            className="rounded-lg px-2.5 py-1 text-[10px] font-bold uppercase"
                            style={{ background: badge.bg, color: badge.color }}
                          >
                            {badge.label}
                          </span>
                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => setArchivingId(archivingId === item.document_id ? null : item.document_id)}
                              className="text-[12px] font-bold transition hover:opacity-75"
                              style={{ color: String(item.status).toLowerCase() === "archived" ? "var(--brand-mid)" : "var(--text-3)" }}
                            >
                              {String(item.status).toLowerCase() === "archived" ? t.unarchive : t.archive}
                            </button>
                            <button
                              onClick={() => router.push(`/analysis/${item.document_id}`)}
                              className="text-[12px] font-bold transition hover:opacity-75"
                              style={{ color: "var(--brand-mid)" }}
                            >
                              {t.openDoc}
                            </button>
                          </div>
                        </div>

                        {archivingId === item.document_id && (
                          <div className="mt-3 rounded-xl px-3 py-2.5 text-[12px]"
                            style={{ background: "rgba(26,53,96,0.06)", border: "1px solid rgba(26,53,96,0.12)", color: "var(--text-2)" }}>
                            <span className="font-semibold">
                              {String(item.status).toLowerCase() === "archived" ? t.restoreConfirm : t.archiveConfirm}
                            </span>{" "}
                            {String(item.status).toLowerCase() === "archived" ? t.restoreDesc : t.archiveDesc}
                            <div className="mt-2 flex gap-2">
                              <button
                                className="rounded-lg px-3 py-1 text-[11px] font-bold text-white transition hover:opacity-80"
                                style={{ background: "var(--brand)" }}
                                onClick={async () => {
                                  const token = getAuthToken();
                                  const newStatus = String(item.status).toLowerCase() === "archived" ? "ready" : "archived";
                                  try {
                                    await fetch(`${BACKEND_URL}/documents/${item.document_id}`, {
                                      method: "PUT",
                                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                                      body: JSON.stringify({ status: newStatus }),
                                    });
                                    setArchivingId(null);
                                    loadDocuments();
                                  } catch { setArchivingId(null); }
                                }}
                              >
                                {String(item.status).toLowerCase() === "archived" ? t.restore : t.archive}
                              </button>
                              <button className="text-[11px] font-bold" style={{ color: "var(--text-3)" }}
                                onClick={() => setArchivingId(null)}>{t.cancel}</button>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="text-right">
                        <p
                          className="text-[13px] font-bold"
                          style={{ color: amt === "No Amount" ? "var(--text-3)" : "var(--text-1)" }}
                        >
                          {amt}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* REFRESH LIST */}
            <div className="mt-6 flex justify-center">
              <button
                onClick={loadDocuments}
                disabled={loading}
                className="flex items-center gap-2 rounded-xl px-6 py-2.5 text-[13px] font-bold transition hover:opacity-80 disabled:opacity-50"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--brand-mid)" }}
              >
                <span className="material-symbols-outlined text-[16px]">refresh</span>
                {t.refreshList}
              </button>
            </div>
            </>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}
