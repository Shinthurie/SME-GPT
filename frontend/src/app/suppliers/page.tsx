"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

type Supplier = {
  name: string; document_count: number;
  total_payable: number; total_receivable: number; net_position: number;
  document_types: string[]; last_transaction: string;
};
type Transaction = {
  document_id: string; document_type: string; date: string;
  amount: number; currency: string; flow_type: string;
  paid_status: string; invoice_status: string; po_status: string; notes: string;
};
type DupGroup = string[];

const TYPE_COLOR: Record<string, string> = {
  invoice:"#2252b5", receipt:"#16a34a", po:"#7c3aed", dn:"#ea6c0a",
};

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function StatusBadge({ val, lang }: { val: string; lang: string }) {
  if (!val || val === "NULL") return null;
  const map: Record<string, string> = {
    paid:"#16a34a", not_paid:"#ea6c0a", overdue:"#dc2626",
    received:"#16a34a", not_received:"#ea6c0a",
    approved:"#16a34a", pending:"#ea6c0a", rejected:"#dc2626",
  };
  const c = map[val.toLowerCase()] || "#64748b";
  return (
    <span className="ml-1 rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase"
      style={{ background: `${c}15`, color: c }}>
      {val.replace(/_/g, " ")}
    </span>
  );
}

function HistoryDrawer({ name, lang, onClose }: { name: string; lang: string; onClose: () => void }) {
  const router = useRouter();
  const [data, setData] = useState<{ transactions: Transaction[]; summary: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/suppliers/${encodeURIComponent(name)}/history`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [name]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: "rgba(0,0,0,0.35)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-[900px] rounded-t-3xl px-5 py-6 shadow-2xl"
        style={{ background: "var(--surface)", maxHeight: "80vh", overflowY: "auto" }}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-[18px] font-extrabold text-[var(--text-1)]">{name}</p>
            <p className="text-[12px] text-[var(--text-3)]">
              {lang === "si" ? "ගනුදෙනු ඉතිහාසය" : "Full Transaction History"}
            </p>
          </div>
          <button onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-xl transition hover:opacity-70"
            style={{ background: "var(--bg)" }}>
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {loading ? (
          <p className="py-8 text-center text-[13px] text-[var(--text-3)]">{lang === "si" ? "පූරණය..." : "Loading..."}</p>
        ) : !data ? (
          <p className="py-8 text-center text-[13px] text-red-500">Failed to load</p>
        ) : (
          <>
            {/* Summary row */}
            <div className="mb-4 grid grid-cols-3 gap-3">
              {[
                { lbl: lang === "si" ? "ගෙව්වා" : "Total Paid",   val: data.summary.total_paid,     color: "#dc2626" },
                { lbl: lang === "si" ? "ලැබුණා" : "Total Received", val: data.summary.total_received, color: "#16a34a" },
                { lbl: lang === "si" ? "ශේෂය"   : "Net",           val: data.summary.net,            color: data.summary.net >= 0 ? "#2252b5" : "#ea6c0a" },
              ].map(({ lbl, val, color }) => (
                <div key={lbl} className="rounded-xl p-3 text-center"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <p className="text-[10px] font-bold uppercase text-[var(--text-3)]">{lbl}</p>
                  <p className="mt-1 text-[13px] font-extrabold" style={{ color }}>
                    {val === 0 ? "—" : `LKR ${val.toLocaleString()}`}
                  </p>
                </div>
              ))}
            </div>

            {/* Transaction list */}
            <div className="space-y-2">
              {data.transactions.length === 0 && (
                <p className="py-4 text-center text-[13px] text-[var(--text-3)]">
                  {lang === "si" ? "ගනුදෙනු නොමැත" : "No transactions"}
                </p>
              )}
              {data.transactions.map((t, i) => (
                <button key={i} onClick={() => router.push(`/analysis/${t.document_id}`)}
                  className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left transition hover:opacity-80"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-[10px] font-bold"
                      style={{ background: TYPE_COLOR[t.document_type] || "#64748b" }}>
                      {(t.document_type || "?").slice(0, 2).toUpperCase()}
                    </span>
                    <div>
                      <p className="text-[13px] font-semibold text-[var(--text-1)]">{t.document_id}</p>
                      <p className="text-[11px] text-[var(--text-3)]">
                        {t.date || "—"}
                        <StatusBadge val={t.paid_status || t.invoice_status || t.po_status} lang={lang} />
                      </p>
                    </div>
                  </div>
                  <span className="text-[13px] font-bold"
                    style={{ color: t.flow_type?.includes("receiv") || t.flow_type?.includes("inflow") ? "#16a34a" : "#dc2626" }}>
                    {t.flow_type?.includes("receiv") || t.flow_type?.includes("inflow") ? "+" : "−"}
                    LKR {t.amount.toLocaleString()}
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function SuppliersPage() {
  const router = useRouter();
  const [lang, setLang]           = useState<AppLanguage>("en");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [search, setSearch]       = useState("");
  const [tab, setTab]             = useState<"all"|"supplier"|"customer">("all");
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const [dupGroups, setDupGroups]   = useState<DupGroup[]>([]);
  const [merging, setMerging]       = useState<DupGroup | null>(null);

  useEffect(() => { setLang(getStoredLanguage()); }, []);
  const t = ui[lang];

  const fetchSuppliers = async (q = "") => {
    const token = getToken();
    if (!token) { router.push("/login"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/suppliers?q=${encodeURIComponent(q)}`, {
        headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
      });
      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
      const data = await res.json();
      if (!data.success) throw new Error(data.message || "Failed");
      setSuppliers(data.suppliers || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally { setLoading(false); }
  };

  const fetchDuplicates = async () => {
    const token = getToken();
    try {
      const res = await fetch(`${BACKEND_URL}/suppliers/duplicates`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (data.success) setDupGroups(data.groups || []);
    } catch { /* non-fatal */ }
  };

  useEffect(() => { fetchSuppliers(); fetchDuplicates(); }, []);
  const handleSearch = (v: string) => { setSearch(v); fetchSuppliers(v); };

  const doMerge = async (canonical: string, aliases: string[]) => {
    const token = getToken();
    await fetch(`${BACKEND_URL}/suppliers/merge`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ canonical_name: canonical, aliases }),
    });
    setMerging(null);
    setDupGroups(g => g.filter(gr => !gr.includes(canonical)));
    fetchSuppliers(search);
  };

  const filtered = suppliers.filter(s => {
    if (tab === "supplier") return s.total_payable > 0;
    if (tab === "customer") return s.total_receivable > 0;
    return true;
  });

  const typeColor = TYPE_COLOR;

  return (
    <MobileShell>
      {historyFor && (
        <HistoryDrawer name={historyFor} lang={lang} onClose={() => setHistoryFor(null)} />
      )}
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[900px] px-4 py-6 sm:px-6">

          <div className="mb-5 flex items-center justify-between">
            <button onClick={() => router.back()}
              className="flex items-center gap-1.5 text-[13px] font-semibold hover:opacity-75 transition"
              style={{ color: "var(--brand-mid)" }}>
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              {t.backToDashboard}
            </button>
            <div className="flex items-center gap-2"><ThemeToggle /><LanguageSwitcher /></div>
          </div>

          <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)]">
            {lang === "si" ? "සැපයුම්කරුවන් සහ ගනුදෙනුකරුවන්" : "Suppliers & Customers"}
          </h1>
          <p className="mt-1 text-[13px] text-[var(--text-2)]">
            {lang === "si" ? "ඔබගේ ලේඛනවල ඇති සියලු ගනුදෙනු පාර්ශ්ව"
              : "All counterparties across your documents with full transaction history."}
          </p>

          {/* Duplicate vendor alert */}
          {dupGroups.map((group, gi) => (
            <div key={gi} className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3"
              style={{ background: "rgba(234,108,10,0.06)", border: "1px solid rgba(234,108,10,0.25)" }}>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px]" style={{ color: "#ea6c0a" }}>warning</span>
                <p className="text-[12px] font-semibold" style={{ color: "#ea6c0a" }}>
                  {lang === "si" ? "සමාන නම් හමු විය:" : "Possible duplicate vendors:"}
                  {" "}{group.join(", ")}
                </p>
              </div>
              <button onClick={() => setMerging(group)}
                className="rounded-lg px-3 py-1.5 text-[11px] font-bold text-white transition hover:opacity-90"
                style={{ background: "#ea6c0a" }}>
                {lang === "si" ? "ඒකාබද්ධ කරන්න" : "Merge"}
              </button>
            </div>
          ))}

          {/* Merge modal */}
          {merging && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)" }}>
              <div className="w-full max-w-sm rounded-2xl p-6" style={{ background: "var(--surface)" }}>
                <p className="mb-4 font-bold text-[var(--text-1)]">
                  {lang === "si" ? "ඒකාබද්ධ කිරීම" : "Merge duplicate vendors"}
                </p>
                <p className="mb-3 text-[12px] text-[var(--text-2)]">
                  {lang === "si" ? "ප‍්‍රධාන නම:" : "Choose canonical name:"}
                </p>
                <div className="space-y-2">
                  {merging.map(name => (
                    <button key={name} onClick={() => doMerge(name, merging)}
                      className="w-full rounded-xl px-4 py-2.5 text-left text-[13px] font-semibold transition hover:opacity-80"
                      style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
                      ✓ {name}
                    </button>
                  ))}
                </div>
                <button onClick={() => setMerging(null)}
                  className="mt-4 w-full rounded-xl py-2 text-[12px] text-[var(--text-3)] hover:opacity-70">
                  {lang === "si" ? "අවලංගු කරන්න" : "Cancel"}
                </button>
              </div>
            </div>
          )}

          {/* Search + tabs */}
          <div className="mt-5 flex items-center gap-2 rounded-xl px-4 py-2.5"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--text-3)" }}>search</span>
            <input type="text" value={search} onChange={e => handleSearch(e.target.value)}
              placeholder={lang === "si" ? "නම සොයන්න..." : "Search by name..."}
              className="flex-1 bg-transparent text-[14px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]" />
          </div>

          <div className="mt-3 flex gap-2">
            {(["all","supplier","customer"] as const).map(tp => (
              <button key={tp} onClick={() => setTab(tp)}
                className="rounded-xl px-4 py-1.5 text-[12px] font-semibold transition"
                style={tab === tp
                  ? { background: "var(--brand-mid)", color: "#fff" }
                  : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                {tp === "all" ? (lang === "si" ? "සියල්ල" : "All")
                  : tp === "supplier" ? (lang === "si" ? "සැපයුම්කරුවන්" : "Suppliers")
                  : (lang === "si" ? "ගනුදෙනුකරුවන්" : "Customers")}
              </button>
            ))}
            <span className="ml-auto text-[12px] text-[var(--text-3)] self-center">
              {filtered.length} {lang === "si" ? "ප‍්‍රතිඵල" : "results"}
            </span>
          </div>

          {loading ? (
            <div className="mt-8 rounded-2xl py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {t.loading}
            </div>
          ) : error ? (
            <div className="mt-5 rounded-2xl px-4 py-3 text-[13px] text-red-600"
              style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
              {error}
            </div>
          ) : filtered.length === 0 ? (
            <div className="mt-8 rounded-2xl py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {lang === "si" ? "සැපයුම්කරුවන් හමු නොවිය." : "No suppliers found."}
            </div>
          ) : (
            <div className="mt-5 space-y-3">
              {filtered.map((s) => (
                <div key={s.name} className="rounded-2xl p-5"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[16px] font-bold text-[var(--text-1)]">{s.name}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {s.document_types.map(dt => (
                          <span key={dt} className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                            style={{ background: `${typeColor[dt] || "#64748b"}18`, color: typeColor[dt] || "#64748b" }}>
                            {dt}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-[11px] text-[var(--text-3)]">
                        {s.document_count} {lang === "si" ? "ලේඛන" : "documents"}
                      </p>
                      {s.last_transaction && (
                        <p className="text-[11px] text-[var(--text-3)]">
                          {lang === "si" ? "අවසාන:" : "Last:"} {s.last_transaction}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-3">
                    {[
                      { label: lang === "si" ? "ලැබිය යුතු" : "Receivable", value: s.total_receivable, color: "#16a34a" },
                      { label: lang === "si" ? "ගෙවිය යුතු" : "Payable",    value: s.total_payable,    color: "#dc2626" },
                      { label: lang === "si" ? "ශේෂය" : "Net Position",      value: s.net_position,     color: s.net_position >= 0 ? "#2252b5" : "#ea6c0a" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="rounded-xl p-3 text-center"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                        <p className="text-[10px] font-bold uppercase text-[var(--text-3)]">{label}</p>
                        <p className="mt-1 text-[13px] font-extrabold" style={{ color }}>
                          {value === 0 ? "—" : `LKR ${value.toLocaleString()}`}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-3 flex items-center gap-4">
                    <button onClick={() => setHistoryFor(s.name)}
                      className="flex items-center gap-1.5 text-[12px] font-bold transition hover:opacity-75"
                      style={{ color: "var(--brand-mid)" }}>
                      <span className="material-symbols-outlined text-[15px]">history</span>
                      {lang === "si" ? "ඉතිහාසය බලන්න" : "View history"}
                    </button>
                    <button onClick={() => router.push(`/repository?q=${encodeURIComponent(s.name)}`)}
                      className="flex items-center gap-1.5 text-[12px] font-bold transition hover:opacity-75"
                      style={{ color: "var(--text-3)" }}>
                      <span className="material-symbols-outlined text-[15px]">folder_open</span>
                      {lang === "si" ? "ලේඛන" : "Documents"}
                    </button>
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
