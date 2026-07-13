"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import BboxOverlayViewer from "@/components/ui/BboxOverlayViewer";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

type PreviewItem = {
  description: string;
  quantity: string | number;
  unit_price: string | number;
  line_total: string | number;
};

type PreviewData = {
  document_type: string; order_id: string; flow_type: string;
  company_name: string; supplier_name: string; date: string;
  currency: string; raw_total_amount: string | number;
  final_total_amount: string | number; payable_amount: string | number;
  cash_return: string | number; received_status: string;
  paid_status: string; tax_amount?: string | number; tax_rate?: string | number;
  items: PreviewItem[];
};

type BulkSession = {
  preview: PreviewData;
  fileName: string;
  arithmeticStatus?: string;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function parseAmt(v: string | number | null | undefined): number {
  const n = Number(String(v ?? "").replace(/,/g, "").replace(/Rs\.?/gi, "").trim());
  return Number.isFinite(n) ? n : 0;
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">{title}</p>
      <div className="mt-3 text-[14px] leading-7 text-[#334155]">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-bold uppercase tracking-wide text-[#94a3b8]">{label}</span>
      {children}
    </div>
  );
}

function TextInput({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder ?? ""}
      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] text-[#0f172a] outline-none focus:border-blue-400"
    />
  );
}

function SelectInput({ value, onChange, options }: {
  value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] text-[#0f172a] outline-none focus:border-blue-400"
    >
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

const DOC_TYPES = [
  { value: "invoice", label: "Invoice" }, { value: "receipt", label: "Receipt" },
  { value: "po", label: "Purchase Order (PO)" }, { value: "dn", label: "Delivery Note (DN)" },
  { value: "unknown", label: "Unknown" },
];
const FLOW_TYPES = [
  { value: "payable", label: "Payable" }, { value: "receivable", label: "Receivable" },
  { value: "cash_inflow", label: "Cash Inflow" }, { value: "cash_outflow", label: "Cash Outflow" },
];
const PAID_STATUSES = [
  { value: "not_paid", label: "Not Paid" }, { value: "paid", label: "Paid" },
  { value: "partial", label: "Partial" }, { value: "NULL", label: "N/A" },
];
const RECV_STATUSES = [
  { value: "not_received", label: "Not Received" }, { value: "received", label: "Received" },
  { value: "partial", label: "Partial" }, { value: "NULL", label: "N/A" },
];

export default function BulkReviewPage() {
  const router = useRouter();
  const pathname = usePathname();
  const sessionId = useMemo(() => {
    const parts = (pathname ?? "").split("/").filter(Boolean);
    return decodeURIComponent(parts[parts.length - 1] ?? "");
  }, [pathname]);

  const [lang, setLang] = useState<AppLanguage>("en");
  const [session, setSession] = useState<BulkSession | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [duplicate, setDuplicate] = useState<{ found: boolean; existingId: string } | null>(null);
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null);

  const t = ui[lang];

  useEffect(() => {
    setLang(getStoredLanguage());
    if (!sessionId) return;
    const raw = sessionStorage.getItem(`sme_bulk_${sessionId}`);
    if (!raw) {
      setError("Session expired — please return to Bulk Upload and try again.");
      return;
    }
    try {
      const data: BulkSession = JSON.parse(raw);
      setSession(data);
      setPreview(data.preview);
    } catch {
      setError("Could not read session data.");
    }
  }, [sessionId]);

  const updateField = (key: keyof PreviewData, value: string) =>
    setPreview((p) => p ? { ...p, [key]: value } : p);

  const updateItem = (idx: number, key: keyof PreviewItem, value: string) =>
    setPreview((p) => {
      if (!p) return p;
      const items = p.items.map((it, i) => {
        if (i !== idx) return it;
        const updated = { ...it, [key]: value };
        if (key === "quantity" || key === "unit_price") {
          const q = parseAmt(updated.quantity), u = parseAmt(updated.unit_price);
          if (q > 0 && u > 0) updated.line_total = +(q * u).toFixed(2);
        }
        return updated;
      });
      const total = +(items.reduce((s, i) => s + parseAmt(i.line_total), 0)).toFixed(2);
      return { ...p, items, final_total_amount: total, payable_amount: total };
    });

  const handleSave = async (force = false) => {
    if (!preview) return;
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }
    setError("");
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, edited_preview: preview, force_save: force }),
      });
      const data = await res.json();

      if (data.duplicate_found && !data.success) {
        setDuplicate({ found: true, existingId: data.existing_document_id || "" });
        setSaving(false);
        return;
      }
      if (!res.ok || !data.success) throw new Error(data.message || "Save failed");

      // Notify bulk-upload widget
      sessionStorage.removeItem(`sme_bulk_${sessionId}`);
      const queue = JSON.parse(localStorage.getItem("sme_bulk_queue") || "[]");
      const updated = queue.map((item: { sessionId: string; status: string; documentId?: string }) =>
        item.sessionId === sessionId
          ? { ...item, status: "done", documentId: data.document_id }
          : item
      );
      localStorage.setItem("sme_bulk_queue", JSON.stringify(updated));
      window.dispatchEvent(new Event("sme-bulk-updated"));

      addNotification({
        type: "success",
        title: "Document Saved",
        message: `${data.document_id} — ${session?.fileName ?? ""}`,
      });
      router.push(`/analysis/${data.document_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    sessionStorage.removeItem(`sme_bulk_${sessionId}`);
    router.back();
  };

  const imageUrl = `${BACKEND_URL}/sessions/${sessionId}/image`;

  if (!session && !error) {
    return (
      <MobileShell>
        <div className="flex min-h-screen items-center justify-center text-[14px] text-[#64748b]">
          Loading session…
        </div>
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6">

          {/* Top bar */}
          <div className="mb-4 flex items-center justify-between gap-3">
            <button
              onClick={handleDiscard}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#2563ff] transition hover:bg-[#eef4ff]"
            >
              <span className="material-symbols-outlined">arrow_back</span>
            </button>

            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <button
                onClick={handleDiscard}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-semibold text-red-600 transition hover:bg-red-50"
              >
                Discard
              </button>
              <button
                onClick={() => handleSave(false)}
                disabled={saving || !preview}
                className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-[13px] font-bold text-white disabled:opacity-40"
                style={{ background: "#16a34a" }}
              >
                <span className="material-symbols-outlined text-[14px]">save</span>
                {saving ? "Saving…" : "Save Document"}
              </button>
            </div>
          </div>

          {/* Page title */}
          <div className="mb-5">
            <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)]">
              {session?.fileName ?? "Bulk Review"}
            </h1>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Review & Confirm Before Saving
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-[18px] border border-red-200 bg-red-50 p-4 text-[14px] text-red-700">
              {error}
            </div>
          )}

          {duplicate?.found && (
            <div className="mb-4 rounded-[18px] border border-amber-200 bg-amber-50 p-4 text-[13px] text-amber-800">
              <span className="font-bold">Duplicate detected</span> — a similar document already exists as{" "}
              <button
                onClick={() => router.push(`/analysis/${duplicate.existingId}`)}
                className="font-bold underline hover:opacity-75"
              >
                {duplicate.existingId}
              </button>
              .{" "}
              <button
                onClick={() => handleSave(true)}
                disabled={saving}
                className="ml-2 rounded-lg bg-amber-600 px-3 py-1 text-[12px] font-bold text-white hover:opacity-90 disabled:opacity-50"
              >
                Save Anyway
              </button>
            </div>
          )}

          {preview && (
            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">

              {/* Left — document image */}
              <div className="rounded-[20px] bg-[#eef2f7] p-3 shadow-sm">
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className="rounded-lg px-3 py-1 text-[10px] font-bold uppercase tracking-wider"
                    style={{ background: "rgba(34,82,181,0.1)", color: "#2252b5" }}
                  >
                    PREVIEW — NOT SAVED
                  </span>
                  <span
                    className="rounded-lg px-2 py-1 text-[10px] font-bold uppercase"
                    style={{
                      background: session?.arithmeticStatus === "matched"
                        ? "rgba(22,163,74,0.1)" : "rgba(234,108,10,0.1)",
                      color: session?.arithmeticStatus === "matched" ? "#16a34a" : "#ea6c0a",
                    }}
                  >
                    {session?.arithmeticStatus === "matched" ? "99% CONFIDENCE" : "VERIFY TOTALS"}
                  </span>
                </div>
                <div className="rounded-[16px] bg-white p-3">
                  <BboxOverlayViewer
                    imageUrl={imageUrl}
                    documentId={`bulk-${sessionId}`}
                    spatialChunksJson={null}
                    activeChunkId={activeChunkId}
                    onChunkSelect={setActiveChunkId}
                  />
                </div>
              </div>

              {/* Right — editable data panel */}
              <div className="space-y-4">

                {/* Header card */}
                <div className="rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">Extracted Data</p>
                      <h2 className="text-[18px] font-extrabold text-[#0f172a]">Document Review</h2>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-xl bg-[#eef4ff] px-3 py-2 text-[12px] font-semibold text-[#2563ff]">
                        {preview.document_type?.toUpperCase() || "UNKNOWN"}
                      </span>
                      <span className="rounded-xl bg-[#f1f5f9] px-3 py-2 text-[12px] text-[#334155]">
                        {preview.currency || "LKR"}
                      </span>
                    </div>
                  </div>

                  {/* Document type + flow type selectors */}
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <Field label="Document Type">
                      <SelectInput
                        value={preview.document_type}
                        onChange={(v) => updateField("document_type", v)}
                        options={DOC_TYPES}
                      />
                    </Field>
                    {preview.document_type !== "dn" && preview.document_type !== "po" && (
                      <Field label="Flow Type">
                        <SelectInput
                          value={preview.flow_type}
                          onChange={(v) => updateField("flow_type", v)}
                          options={FLOW_TYPES}
                        />
                      </Field>
                    )}
                  </div>
                </div>

                {/* METADATA */}
                <InfoCard title="Metadata">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Document No. / Order ID">
                      <TextInput value={preview.order_id || ""} onChange={(v) => updateField("order_id", v)} />
                    </Field>
                    <Field label="Date">
                      <TextInput value={preview.date || ""} onChange={(v) => updateField("date", v)} />
                    </Field>
                    <Field label="Currency">
                      <TextInput value={preview.currency || ""} onChange={(v) => updateField("currency", v)} />
                    </Field>
                  </div>
                </InfoCard>

                {/* PARTIES */}
                <InfoCard title="Parties">
                  <div className="grid grid-cols-1 gap-3">
                    <Field label={
                      preview.document_type === "dn" ? "Delivered By (Supplier)" :
                      ["receivable", "cash_inflow"].includes(preview.flow_type) ? "Customer (Bill To)" :
                      "Supplier (Bill From)"
                    }>
                      <TextInput
                        value={preview.supplier_name || ""}
                        onChange={(v) => updateField("supplier_name", v)}
                      />
                    </Field>
                    <Field label="Our Company">
                      <TextInput
                        value={preview.company_name || ""}
                        onChange={(v) => updateField("company_name", v)}
                      />
                    </Field>
                  </div>
                </InfoCard>

                {/* AMOUNTS — hide for DN */}
                {preview.document_type !== "dn" && (
                  <InfoCard title="Amounts">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Raw Total (OCR)">
                        <TextInput
                          value={String(preview.raw_total_amount ?? "")}
                          onChange={(v) => updateField("raw_total_amount", v)}
                        />
                      </Field>
                      <Field label="Final Total">
                        <TextInput
                          value={String(preview.final_total_amount ?? "")}
                          onChange={(v) => updateField("final_total_amount", v)}
                        />
                      </Field>
                      <Field label="Payable / Receivable Amount">
                        <TextInput
                          value={String(preview.payable_amount ?? "")}
                          onChange={(v) => updateField("payable_amount", v)}
                        />
                      </Field>
                      {(preview.document_type === "receipt") && (
                        <Field label="Cash Return">
                          <TextInput
                            value={String(preview.cash_return ?? "")}
                            onChange={(v) => updateField("cash_return", v)}
                          />
                        </Field>
                      )}
                    </div>
                  </InfoCard>
                )}

                {/* PAYMENT STATUS */}
                {preview.document_type !== "dn" && (
                  <InfoCard title="Payment Status">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Paid Status">
                        <SelectInput
                          value={preview.paid_status || "not_paid"}
                          onChange={(v) => updateField("paid_status", v)}
                          options={PAID_STATUSES}
                        />
                      </Field>
                      <Field label="Received Status">
                        <SelectInput
                          value={preview.received_status || "not_received"}
                          onChange={(v) => updateField("received_status", v)}
                          options={RECV_STATUSES}
                        />
                      </Field>
                    </div>
                  </InfoCard>
                )}

                {/* TAX DETAILS */}
                {preview.document_type !== "dn" && (
                  <InfoCard title="Tax Details">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Tax Rate (%)">
                        <TextInput
                          value={String(preview.tax_rate ?? "")}
                          onChange={(v) => {
                            updateField("tax_rate", v);
                            const rate = parseFloat(v);
                            const subtotal = parseAmt(preview.final_total_amount);
                            if (!isNaN(rate) && subtotal > 0) {
                              const taxAmt = +(subtotal * rate / 100).toFixed(2);
                              updateField("tax_amount", String(taxAmt));
                            }
                          }}
                          placeholder="e.g. 18"
                        />
                      </Field>
                      <Field label="Tax Amount">
                        <TextInput
                          value={String(preview.tax_amount ?? "")}
                          onChange={(v) => updateField("tax_amount", v)}
                        />
                      </Field>
                    </div>
                    <p className="mt-2 text-[11px] text-[#94a3b8]">
                      Sri Lanka standard VAT: 18%. Enter rate to auto-calculate.
                    </p>
                  </InfoCard>
                )}

                {/* LINE ITEMS */}
                {preview.items && preview.items.length > 0 && (
                  <InfoCard title="Line Items">
                    <div className="space-y-2">
                      {/* Header row */}
                      <div className="grid grid-cols-[1fr_64px_90px_90px] gap-2">
                        {["Description", "Qty", "Price", "Total"].map((h) => (
                          <span key={h} className="text-[10px] font-bold uppercase text-[#94a3b8]">{h}</span>
                        ))}
                      </div>
                      {preview.items.map((item, idx) => (
                        <div key={idx} className="grid grid-cols-[1fr_64px_90px_90px] gap-2">
                          <input
                            value={String(item.description)}
                            onChange={(e) => updateItem(idx, "description", e.target.value)}
                            className="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] text-[#0f172a]"
                          />
                          <input
                            value={String(item.quantity)}
                            onChange={(e) => updateItem(idx, "quantity", e.target.value)}
                            className="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] text-right text-[#0f172a]"
                          />
                          <input
                            value={String(item.unit_price)}
                            onChange={(e) => updateItem(idx, "unit_price", e.target.value)}
                            className="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] text-right text-[#0f172a]"
                          />
                          <input
                            value={String(item.line_total)}
                            readOnly
                            className="rounded-lg border border-slate-100 bg-slate-50 px-2 py-1.5 text-[12px] text-right font-semibold text-[#334155]"
                          />
                        </div>
                      ))}
                      <div className="flex justify-end pt-1">
                        <span className="text-[12px] font-bold text-[#0f172a]">
                          Items Total:{" "}
                          {preview.currency || "LKR"}{" "}
                          {preview.items.reduce((s, i) => s + parseAmt(i.line_total), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>
                  </InfoCard>
                )}

                {/* Bottom save button */}
                <div className="flex justify-end gap-2 pb-4">
                  <button
                    onClick={handleDiscard}
                    className="rounded-xl border border-slate-200 px-5 py-2.5 text-[13px] font-semibold text-red-600 transition hover:bg-red-50"
                  >
                    Discard
                  </button>
                  <button
                    onClick={() => handleSave(false)}
                    disabled={saving}
                    className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                    style={{ background: "#16a34a" }}
                  >
                    <span className="material-symbols-outlined text-[16px]">save</span>
                    {saving ? "Saving…" : "Save & Open Document"}
                  </button>
                </div>

              </div>
            </div>
          )}

        </main>
      </div>
    </MobileShell>
  );
}
