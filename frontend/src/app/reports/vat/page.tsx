"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import * as XLSX from "xlsx";

const BACKEND_URL = "http://127.0.0.1:8000";

type VatMonth = {
  month: string;
  tax_total: number;
  document_count: number;
  documents: Array<{document_id:string;document_type:string;supplier_name:string;tax_amount:number;tax_rate:number|null;date:string}>;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function VatReportPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<{total_tax:number;months:VatMonth[]}|null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string|null>(null);

  useEffect(() => { setLang(getStoredLanguage()); }, []);
  const t = ui[lang];

  const fetchReport = async (y: number) => {
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/reports/vat?year=${y}`, {
        headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
      });
      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
      const d = await res.json();
      if (!d.success) throw new Error(d.message || "Failed");
      setData(d);
    } catch (err) { setError(err instanceof Error ? err.message : "Failed"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchReport(year); }, [year]);

  const exportExcel = () => {
    if (!data) return;
    const rows = data.months.flatMap((m) =>
      m.documents.map((d) => ({
        "Month": m.month,
        "Document ID": d.document_id,
        "Type": d.document_type,
        "Supplier/Customer": d.supplier_name,
        "Date": d.date,
        "Tax Rate (%)": d.tax_rate ?? "",
        "Tax Amount (LKR)": d.tax_amount,
      }))
    );
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows), `VAT ${year}`);
    XLSX.writeFile(wb, `vat-report-${year}.xlsx`);
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

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)]">
                {lang === "si" ? "VAT / බදු සාරාංශ වාර්තාව" : "VAT / Tax Summary Report"}
              </h1>
              <p className="mt-1 text-[13px] text-[var(--text-2)]">
                {lang === "si" ? "ලේඛනවල ඇති VAT මාසික සාරාංශය" : "Monthly summary of VAT extracted from your documents."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select value={year} onChange={(e) => setYear(Number(e.target.value))}
                className="field-input rounded-xl border px-3 py-2 text-[13px]">
                {[2024,2025,2026,2027].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
              {data && data.months.length > 0 && (
                <button onClick={exportExcel}
                  className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-[12px] font-bold text-white transition hover:opacity-80"
                  style={{ background: "#16a34a" }}>
                  <span className="material-symbols-outlined text-[15px]">table_view</span>
                  {lang === "si" ? "Excel" : "Export Excel"}
                </button>
              )}
            </div>
          </div>

          {/* Total card */}
          {data && (
            <div className="mt-5 rounded-2xl p-5"
              style={{ background: "var(--brand-tint)", border: "1px solid var(--brand-ring)" }}>
              <p className="text-[11px] font-bold uppercase text-[var(--text-3)]">
                {lang === "si" ? `${year} මුළු VAT` : `Total VAT for ${year}`}
              </p>
              <p className="mt-1 text-[28px] font-extrabold" style={{ color: "var(--brand-mid)" }}>
                LKR {(data.total_tax || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </p>
            </div>
          )}

          {loading ? (
            <div className="mt-8 rounded-2xl py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>{t.loading}</div>
          ) : error ? (
            <div className="mt-5 rounded-2xl px-4 py-3 text-[13px] text-red-600"
              style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>{error}</div>
          ) : !data || data.months.length === 0 ? (
            <div className="mt-8 rounded-2xl py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {lang === "si" ? `${year} සඳහා VAT දත්ත නොමැත.` : `No VAT data found for ${year}.`}
            </div>
          ) : (
            <div className="mt-5 space-y-3">
              {data.months.map((m) => (
                <div key={m.month} className="rounded-2xl overflow-hidden"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <button className="flex w-full items-center justify-between px-5 py-4 text-left"
                    onClick={() => setExpanded(expanded === m.month ? null : m.month)}>
                    <div>
                      <p className="text-[14px] font-bold text-[var(--text-1)]">{m.month}</p>
                      <p className="text-[11px] text-[var(--text-3)]">
                        {m.document_count} {lang === "si" ? "ලේඛන" : "document"}{m.document_count !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[16px] font-extrabold" style={{ color: "var(--brand-mid)" }}>
                        LKR {m.tax_total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </span>
                      <span className="material-symbols-outlined text-[var(--text-3)]">
                        {expanded === m.month ? "expand_less" : "expand_more"}
                      </span>
                    </div>
                  </button>

                  {expanded === m.month && (
                    <div className="border-t px-5 pb-4" style={{ borderColor: "var(--border)" }}>
                      <table className="mt-3 w-full text-[12px]">
                        <thead>
                          <tr className="text-left text-[var(--text-3)]">
                            <th className="pb-2 font-semibold">{lang === "si" ? "ලේඛනය" : "Document"}</th>
                            <th className="pb-2 font-semibold">{lang === "si" ? "සැපයුම්කරු" : "Supplier"}</th>
                            <th className="pb-2 text-right font-semibold">{lang === "si" ? "අනුපාතය" : "Rate"}</th>
                            <th className="pb-2 text-right font-semibold">{lang === "si" ? "VAT (LKR)" : "VAT (LKR)"}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {m.documents.map((d) => (
                            <tr key={d.document_id} className="border-t" style={{ borderColor: "var(--border)" }}>
                              <td className="py-1.5">
                                <button onClick={() => router.push(`/analysis/${d.document_id}`)}
                                  className="font-semibold hover:underline" style={{ color: "var(--brand-mid)" }}>
                                  {d.document_id}
                                </button>
                              </td>
                              <td className="py-1.5 text-[var(--text-2)]">{d.supplier_name || "—"}</td>
                              <td className="py-1.5 text-right text-[var(--text-2)]">
                                {d.tax_rate != null ? `${d.tax_rate}%` : "—"}
                              </td>
                              <td className="py-1.5 text-right font-bold" style={{ color: "var(--brand-mid)" }}>
                                {d.tax_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
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
