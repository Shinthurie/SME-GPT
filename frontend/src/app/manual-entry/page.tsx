"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";
import { getSession } from "@/lib/auth";

const BACKEND_URL = "http://127.0.0.1:8000";

type DocType = "receipt" | "invoice" | "po" | "dn";
type Item = { description: string; quantity: string; unit_price: string; line_total: string };

const DOC_COLORS: Record<DocType, string> = {
  receipt: "#16a34a",
  invoice: "#2252b5",
  po:      "#7c3aed",
  dn:      "#ea6c0a",
};

const DOC_LABELS: Record<DocType, { en: string; si: string; icon: string }> = {
  receipt: { en: "Receipt",        si: "රිසිට්පත",     icon: "receipt_long"    },
  invoice: { en: "Invoice",        si: "ඉන්වොයිස්",    icon: "description"     },
  po:      { en: "Purchase Order", si: "ගෙවීම් නියෝගය", icon: "shopping_cart"   },
  dn:      { en: "Delivery Note",  si: "බෙදාහැරීම",    icon: "local_shipping"  },
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function calcLine(qty: string, price: string): string {
  const q = parseFloat(qty.replace(",", "")) || 0;
  const p = parseFloat(price.replace(",", "")) || 0;
  return q && p ? (q * p).toFixed(2) : "";
}

function sumItems(items: Item[]): number {
  return items.reduce((s, i) => s + (parseFloat(i.line_total.replace(",", "")) || 0), 0);
}

// ── Live Document Preview Component ─────────────────────────────────────────
function DocPreview({
  docType, orderRef, date, company, supplier, items, taxRate, notes, currency, lang,
}: {
  docType: DocType; orderRef: string; date: string; company: string; supplier: string;
  items: Item[]; taxRate: string; notes: string; currency: string; lang: string;
}) {
  const color = DOC_COLORS[docType];
  const subtotal = sumItems(items);
  const taxPct   = parseFloat(taxRate) || 0;
  const taxAmt   = taxPct ? parseFloat((subtotal * taxPct / 100).toFixed(2)) : 0;
  const total    = parseFloat((subtotal + taxAmt).toFixed(2));
  const cur      = currency || "LKR";
  const today    = date || new Date().toLocaleDateString("en-GB");

  return (
    <div className="w-full rounded-2xl overflow-hidden shadow-lg text-[11px]"
      style={{ border: `2px solid ${color}30`, fontFamily: "monospace", background: "white" }}>

      {/* Header */}
      <div className="px-5 py-4 text-white" style={{ background: color }}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[16px] font-extrabold">{company || (lang === "si" ? "ඔබගේ සමාගම" : "Your Company")}</p>
            <p className="mt-0.5 text-[10px] opacity-80">SME-GPT Document System</p>
          </div>
          <div className="text-right">
            <p className="text-[13px] font-bold uppercase">{DOC_LABELS[docType][lang === "si" ? "si" : "en"]}</p>
            <p className="text-[10px] opacity-80">No: {orderRef || "AUTO"}</p>
          </div>
        </div>
        <div className="mt-2 flex justify-between text-[10px] opacity-80">
          <span>{lang === "si" ? "දිනය:" : "Date:"} {today}</span>
          <span className="italic">[{lang === "si" ? "අතින් ඇතුළත් කිරීම" : "MANUAL ENTRY"}]</span>
        </div>
      </div>

      {/* Party block */}
      <div className="px-5 py-3 border-b" style={{ borderColor: `${color}20` }}>
        {docType === "receipt" && (
          <p><span className="font-bold">{lang === "si" ? "ලැබීම:" : "Received from:"}</span> {supplier || "—"}</p>
        )}
        {docType === "invoice" && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[9px] font-bold uppercase opacity-60">{lang === "si" ? "ගනුදෙනුකරු" : "Bill To"}</p>
              <p className="font-bold">{supplier || "—"}</p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase opacity-60">{lang === "si" ? "සමාගම" : "From"}</p>
              <p className="font-bold">{company || "—"}</p>
            </div>
          </div>
        )}
        {(docType === "po" || docType === "dn") && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[9px] font-bold uppercase opacity-60">
                {docType === "po" ? (lang === "si" ? "සැපයුම්කරු" : "Supplier") : (lang === "si" ? "ලබාදෙන්නා" : "Delivered By")}
              </p>
              <p className="font-bold">{supplier || "—"}</p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase opacity-60">
                {docType === "po" ? (lang === "si" ? "ඇණවුම් කළේ" : "Ordered By") : (lang === "si" ? "ලැබුම්කරු" : "Received By")}
              </p>
              <p className="font-bold">{company || "—"}</p>
            </div>
          </div>
        )}
        {notes && <p className="mt-1 text-[10px] opacity-60 italic">{notes}</p>}
      </div>

      {/* Items table */}
      <div className="px-5 py-2">
        <div className="grid text-[9px] font-bold uppercase opacity-60 mb-1"
          style={{ gridTemplateColumns: docType === "dn" ? "1fr 60px 50px" : "1fr 50px 70px 70px" }}>
          <span>{lang === "si" ? "විස්තරය" : "Description"}</span>
          <span className="text-right">{lang === "si" ? "ප්‍රමා." : "Qty"}</span>
          {docType !== "dn" && <span className="text-right">{lang === "si" ? "ඒකක මිල" : "Price"}</span>}
          <span className="text-right">{docType === "dn" ? (lang === "si" ? "ඒකකය" : "Unit") : (lang === "si" ? "එකතුව" : "Total")}</span>
        </div>
        {items.filter(i => i.description).map((item, idx) => (
          <div key={idx} className="grid py-0.5 border-t" style={{
            gridTemplateColumns: docType === "dn" ? "1fr 60px 50px" : "1fr 50px 70px 70px",
            borderColor: "#f0f0f0",
          }}>
            <span className="truncate">{item.description}</span>
            <span className="text-right">{item.quantity || "1"}</span>
            {docType !== "dn" && <span className="text-right">{item.unit_price || "—"}</span>}
            <span className="text-right font-semibold">
              {docType === "dn" ? "pcs" : (item.line_total || "—")}
            </span>
          </div>
        ))}
        {items.filter(i => i.description).length === 0 && (
          <p className="py-2 text-center opacity-40 italic">
            {lang === "si" ? "අයිතම එක් කරන්න..." : "Add items below..."}
          </p>
        )}
      </div>

      {/* Totals */}
      {docType !== "dn" && subtotal > 0 && (
        <div className="px-5 py-3 border-t" style={{ borderColor: `${color}20` }}>
          {taxPct > 0 && (
            <>
              <div className="flex justify-between opacity-70">
                <span>{lang === "si" ? "උප එකතුව" : "Subtotal"}</span>
                <span>{cur} {subtotal.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
              </div>
              <div className="flex justify-between opacity-70">
                <span>Tax ({taxPct}%)</span>
                <span>{cur} {taxAmt.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
              </div>
            </>
          )}
          <div className="flex justify-between mt-1 font-extrabold text-[13px]" style={{ color }}>
            <span>{lang === "si" ? "මුළු එකතුව" : "TOTAL"}</span>
            <span>{cur} {total.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-5 py-2 text-center text-[9px] opacity-50 border-t" style={{ borderColor: `${color}15` }}>
        {lang === "si"
          ? `ලේඛනය: ${orderRef || "AUTO"} · SME-GPT මගින් නිර්මාණය කෙරිණි`
          : `Document: ${orderRef || "AUTO"} · Created via SME-GPT`}
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function ManualEntryPage() {
  const router = useRouter();
  const [lang, setLang]         = useState<AppLanguage>("en");
  const [docType, setDocType]   = useState<DocType>("receipt");
  const [orderRef, setOrderRef] = useState("");
  const [date, setDate]         = useState(new Date().toISOString().slice(0, 10));
  const [company, setCompany]   = useState("");
  const [supplier, setSupplier] = useState("");
  const [currency, setCurrency] = useState("LKR");
  const [taxRate, setTaxRate]   = useState("");
  const [notes, setNotes]       = useState("");
  const [items, setItems]       = useState<Item[]>([
    { description: "", quantity: "1", unit_price: "", line_total: "" },
  ]);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");
  const [success, setSuccess]   = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
    getSession().then(s => { if (s?.companyName) setCompany(s.companyName); });
  }, []);

  const t = ui[lang];

  const updateItem = (idx: number, key: keyof Item, val: string) => {
    const next = [...items];
    next[idx] = { ...next[idx], [key]: val };
    if (key === "quantity" || key === "unit_price") {
      next[idx].line_total = calcLine(
        key === "quantity" ? val : next[idx].quantity,
        key === "unit_price" ? val : next[idx].unit_price,
      );
    }
    setItems(next);
  };

  const addItem = () => setItems(i => [...i, { description: "", quantity: "1", unit_price: "", line_total: "" }]);
  const removeItem = (idx: number) => setItems(i => i.filter((_, j) => j !== idx));

  const handleSave = async () => {
    if (!supplier.trim()) { setError(lang === "si" ? "සැපයුම්කරු/ගනුදෙනුකරු නම ඇතුළත් කරන්න." : "Please enter supplier/customer name."); return; }
    const validItems = items.filter(i => i.description.trim());
    if (!validItems.length) { setError(lang === "si" ? "අය‌ිතමයක් හෝ ඇතුළත් කරන්න." : "Add at least one item."); return; }

    setSaving(true); setError(""); setSuccess("");
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    const body = {
      document_type: docType,
      order_id:      orderRef.trim() || undefined,
      date:          date,
      supplier_name: supplier.trim(),
      currency:      currency,
      items:         validItems,
      tax_rate:      taxRate ? parseFloat(taxRate) : undefined,
      notes:         notes.trim() || undefined,
      force_save:    false,
    };

    try {
      const res = await fetch(`${BACKEND_URL}/documents/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        setError(data.message || "Save failed.");
        return;
      }

      setSuccess(data.document_id);
      addNotification({
        type: "success",
        title: lang === "si" ? "ලේඛනය නිර්මාණය කෙරිණි" : "Document Created",
        message: `${data.document_id} — ${DOC_LABELS[docType][lang === "si" ? "si" : "en"]}`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  const color = DOC_COLORS[docType];

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[1100px] px-4 py-6 sm:px-6">

          {/* Top bar */}
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
            {lang === "si" ? "ලේඛනයක් අතින් නිර්මාණය කරන්න" : "Create Document Manually"}
          </h1>
          <p className="mt-1 text-[13px] text-[var(--text-2)]">
            {lang === "si"
              ? "බිල්පතක් නොලැබුණු හෝ නැතිවූ අවස්ථාවලදී — ගෙවීම සටහන් කර ලේඛනය සාදන්න."
              : "No bill received, or lost a bill? Fill in the details and create your own receipt or invoice."}
          </p>

          <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_380px]">

            {/* ── LEFT: Form ───────────────────────────────────────────────── */}
            <div className="space-y-5">

              {/* Document type tabs */}
              <div>
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
                  {lang === "si" ? "ලේඛන වර්ගය" : "Document Type"}
                </p>
                <div className="flex flex-wrap gap-2">
                  {(["receipt","invoice","po","dn"] as DocType[]).map((dt) => (
                    <button key={dt} onClick={() => setDocType(dt)}
                      className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-[13px] font-semibold transition"
                      style={docType === dt
                        ? { background: DOC_COLORS[dt], color: "#fff", boxShadow: `0 2px 8px ${DOC_COLORS[dt]}44` }
                        : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                      <span className="material-symbols-outlined text-[16px]">{DOC_LABELS[dt].icon}</span>
                      {DOC_LABELS[dt][lang === "si" ? "si" : "en"]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Core fields grid */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "දිනය" : "Date"}
                  </label>
                  <input type="date" value={date} onChange={e => setDate(e.target.value)}
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition" />
                </div>
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "යොමු අංකය (ස්වයංක්‍රීය)" : "Reference No. (auto if blank)"}
                  </label>
                  <input value={orderRef} onChange={e => setOrderRef(e.target.value)}
                    placeholder={lang === "si" ? "ස්වයංක්‍රීයව සාදනු ලැබේ" : "Auto-generated"}
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition" />
                </div>
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "ඔබගේ සමාගම" : "Your Company"}{" "}
                    <span className="text-[10px] opacity-50">({lang === "si" ? "ස්වයංක්‍රීය" : "auto"})</span>
                  </label>
                  <input value={company} readOnly
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px]"
                    style={{ background: "var(--input-bg-ro)", cursor: "not-allowed" }} />
                </div>
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {docType === "dn" || docType === "po"
                      ? (lang === "si" ? "සැපයුම්කරු" : "Supplier *")
                      : docType === "invoice"
                      ? (lang === "si" ? "ගනුදෙනුකරු" : "Customer *")
                      : (lang === "si" ? "ගෙව්වේ / ලැබුනේ" : "Paid To / Received From *")}
                  </label>
                  <input value={supplier} onChange={e => setSupplier(e.target.value)}
                    placeholder={lang === "si" ? "නම ඇතුළත් කරන්න" : "Enter name"}
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition" />
                </div>
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "මුදල් ඒකකය" : "Currency"}
                  </label>
                  <select value={currency} onChange={e => setCurrency(e.target.value)}
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition">
                    {["LKR","USD","EUR","GBP","SGD","AUD"].map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                {docType !== "dn" && (
                  <div>
                    <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                      {lang === "si" ? "VAT / බදු % (නොමැති නම් හිස් කරන්න)" : "Tax / VAT % (leave blank if none)"}
                    </label>
                    <input type="number" min="0" max="100" value={taxRate} onChange={e => setTaxRate(e.target.value)}
                      placeholder="15"
                      className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition" />
                  </div>
                )}
                <div className="sm:col-span-2">
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "සටහන් (විකල්ප)" : "Notes (optional)"}
                  </label>
                  <input value={notes} onChange={e => setNotes(e.target.value)}
                    placeholder={lang === "si" ? "උදා: මුදලින් ගෙව්වා, බිල්පතක් නොලැබිණි" : "e.g. Paid in cash, no bill received"}
                    className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition" />
                </div>
              </div>

              {/* Items table */}
              <div>
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
                  {lang === "si" ? "අයිතම" : "Items"}
                </p>
                <div className="space-y-2">
                  {/* Header */}
                  <div className={`grid gap-2 px-1 text-[10px] font-bold uppercase text-[var(--text-3)] ${docType === "dn" ? "grid-cols-[1fr_80px]" : "grid-cols-[1fr_70px_90px_90px_32px]"}`}>
                    <span>{lang === "si" ? "විස්තරය" : "Description"}</span>
                    <span className="text-right">{lang === "si" ? "ප්‍රමාණය" : "Qty"}</span>
                    {docType !== "dn" && <span className="text-right">{lang === "si" ? "ඒකක මිල" : "Unit Price"}</span>}
                    {docType !== "dn" && <span className="text-right">{lang === "si" ? "එකතුව" : "Line Total"}</span>}
                  </div>

                  {items.map((item, idx) => (
                    <div key={idx} className={`grid gap-2 items-center ${docType === "dn" ? "grid-cols-[1fr_80px_32px]" : "grid-cols-[1fr_70px_90px_90px_32px]"}`}>
                      <input value={item.description} onChange={e => updateItem(idx, "description", e.target.value)}
                        placeholder={lang === "si" ? "විස්තරය" : "Item description"}
                        className="field-input rounded-xl border px-3 py-2 text-[13px] transition" />
                      <input value={item.quantity} onChange={e => updateItem(idx, "quantity", e.target.value)}
                        type="number" min="0" step="any"
                        className="field-input rounded-xl border px-3 py-2 text-[13px] transition text-right" />
                      {docType !== "dn" && (
                        <input value={item.unit_price} onChange={e => updateItem(idx, "unit_price", e.target.value)}
                          type="number" min="0" step="any" placeholder="0.00"
                          className="field-input rounded-xl border px-3 py-2 text-[13px] transition text-right" />
                      )}
                      {docType !== "dn" && (
                        <input value={item.line_total} readOnly
                          className="rounded-xl border px-3 py-2 text-[13px] text-right font-semibold"
                          style={{ background: "var(--input-bg-ro)", border: "1px solid var(--border)", cursor: "not-allowed" }} />
                      )}
                      <button onClick={() => removeItem(idx)} disabled={items.length === 1}
                        className="flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-red-50 hover:text-red-500 disabled:opacity-30"
                        style={{ color: "var(--text-3)" }}>
                        <span className="material-symbols-outlined text-[16px]">close</span>
                      </button>
                    </div>
                  ))}
                </div>

                <button onClick={addItem}
                  className="mt-3 flex items-center gap-1.5 rounded-xl px-4 py-2 text-[12px] font-semibold transition hover:opacity-80"
                  style={{ background: `${color}12`, color, border: `1px solid ${color}25` }}>
                  <span className="material-symbols-outlined text-[15px]">add</span>
                  {lang === "si" ? "අයිතමයක් එක් කරන්න" : "Add item"}
                </button>
              </div>

              {/* Error / Success */}
              {error && (
                <div className="rounded-xl px-4 py-3 text-[13px] text-red-600"
                  style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)" }}>
                  {error}
                </div>
              )}

              {success && (
                <div className="rounded-xl px-5 py-4 text-[13px]"
                  style={{ background: "rgba(22,163,74,0.06)", border: "1px solid rgba(22,163,74,0.2)", color: "#16a34a" }}>
                  <p className="font-bold">
                    <span className="material-symbols-outlined text-[16px] align-bottom mr-1">check_circle</span>
                    {lang === "si" ? `${success} — සාර්ථකව සේව් විය!` : `${success} — saved successfully!`}
                  </p>
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => router.push(`/analysis/${success}`)}
                      className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-white transition hover:opacity-90"
                      style={{ background: "#16a34a" }}>
                      {lang === "si" ? "ලේඛනය විවෘත කරන්න" : "Open document"}
                    </button>
                    <button onClick={() => { setSuccess(""); setOrderRef(""); setSupplier(""); setNotes(""); setTaxRate(""); setItems([{ description: "", quantity: "1", unit_price: "", line_total: "" }]); }}
                      className="rounded-lg px-3 py-1.5 text-[12px] font-semibold transition hover:opacity-80"
                      style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}>
                      {lang === "si" ? "නව ලේඛනයක්" : "New document"}
                    </button>
                  </div>
                </div>
              )}

              {/* Save button */}
              {!success && (
                <button onClick={handleSave} disabled={saving}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
                  style={{ background: color }}>
                  {saving
                    ? <><span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                        {lang === "si" ? "ලේඛනය නිර්මාණය කරමින්..." : "Creating document..."}</>
                    : <><span className="material-symbols-outlined text-[18px]">save</span>
                        {lang === "si" ? "ලේඛනය සුරකින්න සහ නිර්මාණය කරන්න" : "Save & Generate Document"}</>}
                </button>
              )}
            </div>

            {/* ── RIGHT: Live Preview ───────────────────────────────────── */}
            <div className="hidden lg:block">
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
                {lang === "si" ? "සජීවී පූර්ව දැකීම" : "Live Preview"}
              </p>
              <div className="sticky top-6">
                <DocPreview
                  docType={docType} orderRef={orderRef} date={date}
                  company={company} supplier={supplier} items={items}
                  taxRate={taxRate} notes={notes} currency={currency} lang={lang}
                />
                <p className="mt-2 text-center text-[10px] text-[var(--text-3)]">
                  {lang === "si"
                    ? "සුරකිනු ලැබූ විට Python Pillow ශෛලිය ජනනය කෙරේ"
                    : "Final PNG generated by Pillow on save"}
                </p>
              </div>
            </div>

          </div>
        </main>
        <BottomNav />
      </div>
    </MobileShell>
  );
}
