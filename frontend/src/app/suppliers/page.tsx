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
  name: string;
  document_count: number;
  total_payable: number;
  total_receivable: number;
  net_position: number;
  document_types: string[];
  last_transaction: string;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function SuppliersPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => { setLang(getStoredLanguage()); }, []);
  const t = ui[lang];

  const fetchSuppliers = async (q = "") => {
    const token = getAuthToken();
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

  useEffect(() => { fetchSuppliers(); }, []);

  const handleSearch = (v: string) => { setSearch(v); fetchSuppliers(v); };

  const typeColor: Record<string, string> = {
    invoice: "#2252b5", receipt: "#16a34a", po: "#7c3aed", dn: "#ea6c0a",
  };

  return (
    <MobileShell>
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
            {lang === "si"
              ? "ඔබගේ ලේඛනවල ඇති සියලු ගනුදෙනු පාර්ශ්ව"
              : "All counterparties across your documents with transaction history."}
          </p>

          {/* Search */}
          <div className="mt-5 flex items-center gap-2 rounded-xl px-4 py-2.5"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--text-3)" }}>search</span>
            <input
              type="text" value={search} onChange={(e) => handleSearch(e.target.value)}
              placeholder={lang === "si" ? "නම සොයන්න..." : "Search by name..."}
              className="flex-1 bg-transparent text-[14px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]"
            />
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
          ) : suppliers.length === 0 ? (
            <div className="mt-8 rounded-2xl py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {lang === "si" ? "සැපයුම්කරුවන් හමු නොවිය." : "No suppliers found."}
            </div>
          ) : (
            <div className="mt-5 space-y-3">
              {suppliers.map((s) => (
                <div key={s.name}
                  className="rounded-2xl p-5"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[16px] font-bold text-[var(--text-1)]">{s.name}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {s.document_types.map((dt) => (
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

                  <button
                    onClick={() => router.push(`/repository?q=${encodeURIComponent(s.name)}`)}
                    className="mt-3 text-[12px] font-bold transition hover:opacity-75"
                    style={{ color: "var(--brand-mid)" }}>
                    {lang === "si" ? "ලේඛන බලන්න →" : "View documents →"}
                  </button>
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
