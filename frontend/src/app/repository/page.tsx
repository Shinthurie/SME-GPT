"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage } from "@/lib/i18n";

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
};

type TabType = "all" | "invoice" | "po" | "dn" | "receipt";

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

export default function RepositoryPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [tab, setTab] = useState<TabType>("all");
  const [documents, setDocuments] = useState<RepoDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { setLang(getStoredLanguage()); }, []);

  useEffect(() => {
    const fetch_ = async () => {
      const token = getAuthToken();
      if (!token) { router.push("/login"); return; }

      try {
        const res = await fetch(`${BACKEND_URL}/documents`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || "Failed to fetch.");
        setDocuments(data.documents || []);
      } catch (err: any) {
        setError(err.message || "Failed to fetch documents.");
      } finally {
        setLoading(false);
      }
    };
    fetch_();
  }, [router]);

  const filtered = useMemo(
    () => (tab === "all" ? documents : documents.filter((d) => d.document_type === tab)),
    [tab, documents]
  );

  const tabLabel = (v: TabType) => {
    if (lang === "si") {
      return { all: "සියල්ල", invoice: "ඉන්වොයිස්", po: "PO", dn: "DN", receipt: "රිසිට්" }[v];
    }
    return { all: "All", invoice: "Invoice", po: "PO", dn: "DN", receipt: "Receipt" }[v];
  };

  const formatAmount = (item: RepoDocument) => {
    const amt = isUsable(item.payable_amount)
      ? item.payable_amount
      : isUsable(item.final_total_amount)
      ? item.final_total_amount
      : isUsable(item.raw_total_amount)
      ? item.raw_total_amount
      : null;
    if (!amt) return "No Amount";
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
                Repository
              </h1>
              <p className="mt-0.5 text-[12px] text-[var(--text-3)]">
                {lang === "si" ? "SME-ව්‍යාපාර ලේඛන" : "SME business documents"}
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

          {/* Tabs */}
          <div className="mb-5 flex flex-wrap gap-2">
            {(["all", "invoice", "po", "dn", "receipt"] as TabType[]).map((v) => (
              <button
                key={v}
                onClick={() => setTab(v)}
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

          {/* Content */}
          {loading ? (
            <div className="rounded-2xl px-4 py-8 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              Loading documents…
            </div>
          ) : error ? (
            <div className="rounded-2xl px-4 py-6 text-center text-[14px] text-red-600"
              style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
              {error}
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-2xl px-4 py-8 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              No documents found.
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((item) => {
                const m = typeMap[item.document_type] ?? typeMap.unknown;
                const amt = formatAmount(item);
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

                        <div className="mt-3 flex items-center justify-between gap-4">
                          <span
                            className="rounded-lg px-2.5 py-1 text-[10px] font-bold uppercase"
                            style={{ background: "rgba(22,163,74,0.1)", color: "#16a34a" }}
                          >
                            ready
                          </span>
                          <button
                            onClick={() => router.push(`/analysis/${item.document_id}`)}
                            className="text-[12px] font-bold transition hover:opacity-75"
                            style={{ color: "var(--brand-mid)" }}
                          >
                            OPEN →
                          </button>
                        </div>
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
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}
