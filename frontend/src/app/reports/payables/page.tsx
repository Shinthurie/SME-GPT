"use client";
/**
 * Payables Analysis — avoids double-counting PO + Invoice for the same transaction.
 *
 * Outstanding Invoices  = confirmed money owed (real obligation)
 * Committed POs         = promised but not yet invoiced (future obligation)
 * Settled               = already paid (historical record)
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/layout/PageShell";
import { getStoredLanguage, AppLanguage } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

type PayableRow = {
  document_id: string; document_type: string; supplier_name: string;
  amount: number; currency: string; date: string; days_old: number;
  paid_status: string; po_status: string; order_id: string; notes: string;
};
type Summary = {
  outstanding_total: number; committed_total: number; settled_total: number;
  outstanding_count: number; committed_count: number; settled_count: number;
};

type Tab = "outstanding" | "committed" | "settled";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function StatusBadge({ status, type }: { status: string; type: "paid" | "po" }) {
  if (!status || status === "NULL" || status === "") return null;
  const colors: Record<string, string> = {
    paid: "#16a34a", not_paid: "#ea6c0a", overdue: "#dc2626",
    pending: "#ea6c0a", approved: "#2252b5", fulfilled: "#16a34a",
    partially_delivered: "#0891b2", cancelled: "#dc2626", rejected: "#dc2626",
  };
  const c = colors[status.toLowerCase()] || "#64748b";
  return (
    <span className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
      style={{ background: `${c}15`, color: c }}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function AgeBadge({ days }: { days: number }) {
  if (!days) return null;
  const color = days > 60 ? "#dc2626" : days > 30 ? "#ea6c0a" : "#64748b";
  return (
    <span className="text-[10px] font-semibold" style={{ color }}>
      {days}d old
    </span>
  );
}

function PayableTable({ rows, currency = "LKR", lang, router, emptyMsg }: {
  rows: PayableRow[]; currency?: string; lang: string;
  router: ReturnType<typeof useRouter>; emptyMsg: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-2xl py-12 text-center text-[14px] text-[var(--text-3)]"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        {emptyMsg}
      </div>
    );
  }

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      {/* Table header */}
      <div className="grid gap-3 px-5 py-3 text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]"
        style={{ gridTemplateColumns: "1fr 1fr 100px 80px 80px", borderBottom: "1px solid var(--border)" }}>
        <span>{lang === "si" ? "ලේඛනය" : "Document"}</span>
        <span>{lang === "si" ? "සැපයුම්කරු" : "Supplier / Party"}</span>
        <span className="text-right">{lang === "si" ? "මුදල" : "Amount"}</span>
        <span className="text-center">{lang === "si" ? "දිනය" : "Date"}</span>
        <span className="text-center">{lang === "si" ? "තත්ත්වය" : "Status"}</span>
      </div>

      {rows.map((row, i) => (
        <button key={i} onClick={() => router.push(`/analysis/${row.document_id}`)}
          className="grid w-full gap-3 px-5 py-4 text-left transition hover:bg-[var(--surface-2)]"
          style={{ gridTemplateColumns: "1fr 1fr 100px 80px 80px", borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : "none" }}>

          {/* Document */}
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-[var(--text-1)]">{row.document_id}</p>
            <p className="text-[11px] uppercase font-medium" style={{ color: row.document_type === "po" ? "#7c3aed" : "#2252b5" }}>
              {row.document_type?.toUpperCase()}
              {row.order_id && row.order_id !== row.document_id && (
                <span className="ml-1 normal-case font-normal text-[var(--text-3)]">· {row.order_id}</span>
              )}
            </p>
          </div>

          {/* Supplier */}
          <div className="min-w-0">
            <p className="truncate text-[13px] text-[var(--text-1)]">{row.supplier_name}</p>
            {row.notes && (
              <p className="truncate text-[11px] text-[var(--text-3)]">{row.notes}</p>
            )}
          </div>

          {/* Amount */}
          <div className="text-right">
            <p className="text-[14px] font-extrabold text-[var(--text-1)]">
              {row.currency || currency} {row.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </p>
          </div>

          {/* Date + age */}
          <div className="flex flex-col items-center gap-0.5">
            <p className="text-[11px] text-[var(--text-2)]">{row.date || "—"}</p>
            <AgeBadge days={row.days_old} />
          </div>

          {/* Status */}
          <div className="flex items-center justify-center gap-1">
            {row.document_type === "po"
              ? <StatusBadge status={row.po_status} type="po" />
              : <StatusBadge status={row.paid_status} type="paid" />}
          </div>
        </button>
      ))}
    </div>
  );
}

export default function PayablesPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [tab, setTab]   = useState<Tab>("outstanding");
  const [data, setData] = useState<{ outstanding: PayableRow[]; committed: PayableRow[]; settled: PayableRow[]; summary: Summary } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
    const token = getToken();
    if (!token) { router.push("/login"); return; }
    fetch(`${BACKEND_URL}/reports/payables`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { if (!d.success) throw new Error(d.message); setData(d); })
      .catch(e => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const s = data?.summary;

  const TABS: { key: Tab; label_en: string; label_si: string; count: number; total: number; color: string }[] = [
    {
      key: "outstanding", color: "#dc2626",
      label_en: "Outstanding Invoices", label_si: "ගෙවීමට ඇති ඉන්වොයිස්",
      count: s?.outstanding_count ?? 0, total: s?.outstanding_total ?? 0,
    },
    {
      key: "committed", color: "#7c3aed",
      label_en: "Committed POs", label_si: "ගෙවීමට ඇති PO",
      count: s?.committed_count ?? 0, total: s?.committed_total ?? 0,
    },
    {
      key: "settled", color: "#16a34a",
      label_en: "Settled", label_si: "ගෙව්වා",
      count: s?.settled_count ?? 0, total: s?.settled_total ?? 0,
    },
  ];

  return (
    <PageShell
      backLabel={lang === "si" ? "ආපසු" : "Back"}
      title={lang === "si" ? "ගෙවිය යුතු විශ්ලේෂණය" : "Payables Analysis"}
      subtitle={lang === "si"
        ? "PO සහ ඉන්වොයිස් දෙගුණ ගණනය නොකර නිවැරදි ගෙවිය යුතු ශේෂය"
        : "True outstanding liability — POs and Invoices are shown separately to avoid double-counting the same transaction."}
      width="standard"
    >
      {/* Explanation banner */}
      <div className="mb-5 rounded-2xl px-5 py-4 text-[12px]"
        style={{ background: "rgba(34,82,181,0.05)", border: "1px solid rgba(34,82,181,0.15)" }}>
        <p className="font-semibold text-[var(--text-1)] mb-1">
          {lang === "si" ? "ඇයි PO සහ ඉන්වොයිස් වෙන් කළේ?" : "Why PO and Invoice are separated"}
        </p>
        <p className="text-[var(--text-2)]">
          {lang === "si"
            ? "PO යනු ගෙවීමේ පොරොන්දුවක් පමණි — ඉන්වොයිසයක් නොලැබෙන තෙක් මුදල් නොවෙනස් වේ. ඒ නිසා PO සහ ඒ සඳහා ලැබෙන ඉන්වොයිස දෙකම ගෙවිය යුතු ලෙස ගණනය කළ හොත් ශේෂය දෙගුණ වේ."
            : "A PO is only a promise to pay — no money moves until an Invoice arrives. If both the PO and its Invoice are counted as payable, your liability is overstated. Fulfilled POs are excluded here; their Invoice appears under Outstanding instead."}
        </p>
      </div>

      {/* Summary cards */}
      {s && (
        <div className="mb-5 grid grid-cols-3 gap-3">
          {TABS.map(tb => (
            <div key={tb.key} className="rounded-2xl p-4"
              style={{ background: `${tb.color}08`, border: `1px solid ${tb.color}20` }}>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: tb.color }}>
                {lang === "si" ? tb.label_si : tb.label_en}
              </p>
              <p className="mt-1 text-[20px] font-extrabold text-[var(--text-1)]">
                LKR {tb.total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </p>
              <p className="mt-0.5 text-[11px] text-[var(--text-3)]">
                {tb.count} {lang === "si" ? "ලේඛන" : "documents"}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Real liability highlight */}
      {s && (
        <div className="mb-5 flex items-center justify-between rounded-2xl px-5 py-4"
          style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-red-600">
              {lang === "si" ? "ඇත්ත ගෙවිය යුතු මුදල (ඉන්වොයිස් පමණ)" : "True Payable (Invoices only — no POs)"}
            </p>
            <p className="mt-0.5 text-[12px] text-[var(--text-2)]">
              {lang === "si"
                ? "PO ඉවත් කොට ඉතිරි ශේෂය — ගෙවීම් කළ හැකි ඇත්ත ශේෂය"
                : "This is the amount your business actually owes right now, with no PO double-counting"}
            </p>
          </div>
          <p className="text-[22px] font-extrabold text-red-600 shrink-0 ml-4">
            LKR {s.outstanding_total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-2">
        {TABS.map(tb => (
          <button key={tb.key} onClick={() => setTab(tb.key)}
            className="flex items-center gap-2 rounded-xl px-4 py-2 text-[12px] font-semibold transition"
            style={tab === tb.key
              ? { background: tb.color, color: "#fff", boxShadow: `0 2px 8px ${tb.color}40` }
              : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
            {lang === "si" ? tb.label_si : tb.label_en}
            <span className="rounded-full px-1.5 py-0.5 text-[10px] font-bold"
              style={tab === tb.key ? { background: "rgba(255,255,255,0.25)" } : { background: "var(--bg)" }}>
              {tb.count}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="rounded-2xl py-12 text-center text-[14px] text-[var(--text-3)]"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {lang === "si" ? "පූරණය..." : "Loading…"}
        </div>
      ) : error ? (
        <div className="rounded-2xl px-5 py-4 text-[13px] text-red-600"
          style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
          {error}
        </div>
      ) : (
        <>
          {tab === "outstanding" && (
            <>
              <p className="mb-3 text-[12px] text-[var(--text-3)]">
                {lang === "si"
                  ? "ඉදිරි ගෙවිය යුතු ඉන්වොයිස් — ඔබ ඇත්තෙන්ම ගෙවිය යුතු මුදල"
                  : "Unpaid invoices and receipts — the actual confirmed amount your business owes right now."}
              </p>
              <PayableTable rows={data?.outstanding ?? []} lang={lang} router={router}
                emptyMsg={lang === "si" ? "ගෙවීමට ඇති ඉන්වොයිස් නොමැත" : "No outstanding invoices — all clear!"} />
            </>
          )}
          {tab === "committed" && (
            <>
              <p className="mb-3 text-[12px] text-[var(--text-3)]">
                {lang === "si"
                  ? "ඔබ ඔතා ඇති PO — ඉන්වොයිසය ලැබෙන විට ගෙවිය යුතු වේ. Fulfilled PO ඉවත් කොට ඇත."
                  : "Active POs you have raised — funds will be owed when the Invoice arrives. Fulfilled POs are excluded (their Invoice is in Outstanding)."}
              </p>
              <PayableTable rows={data?.committed ?? []} lang={lang} router={router}
                emptyMsg={lang === "si" ? "ක‍ාරිය PO නොමැත" : "No active committed POs."} />
            </>
          )}
          {tab === "settled" && (
            <>
              <p className="mb-3 text-[12px] text-[var(--text-3)]">
                {lang === "si" ? "ගෙව්වා ලේඛන" : "Documents where payment has been recorded as settled."}
              </p>
              <PayableTable rows={data?.settled ?? []} lang={lang} router={router}
                emptyMsg={lang === "si" ? "ගෙව්වා ලේඛන නොමැත" : "No settled payables yet."} />
            </>
          )}
        </>
      )}
    </PageShell>
  );
}
