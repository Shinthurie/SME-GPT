"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

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
  paid_status: string; items: PreviewItem[];
};

type StreamEvent = {
  stage?: string;
  message?: string;
  step?: number;
  preview?: PreviewData;
  session_id?: string;
};

const BACKEND_URL = "http://127.0.0.1:8000";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

const FIELD_ROWS: [string, string][] = [
  ["document_type", "Document Type"], ["order_id", "Order ID"],
  ["flow_type", "Flow Type"], ["company_name", "Company Name"],
  ["supplier_name", "Customer / Supplier"], ["date", "Date"],
  ["currency", "Currency"], ["raw_total_amount", "Raw Total (OCR)"],
  ["final_total_amount", "Final Total"], ["payable_amount", "Payable / Receivable"],
  ["cash_return", "Cash Return"], ["received_status", "Received Status"],
  ["paid_status", "Paid Status"],
];

const SELECT_OPTS: Record<string, { label: string; value: string }[]> = {
  flow_type: [
    { label: "Select…", value: "" },
    { label: "Payable", value: "payable" }, { label: "Receivable", value: "receivable" },
    { label: "Income", value: "income" }, { label: "Expense", value: "expense" },
  ],
  document_type: [
    { label: "Select…", value: "" },
    { label: "Invoice", value: "invoice" }, { label: "Receipt", value: "receipt" },
    { label: "PO", value: "po" }, { label: "DN", value: "dn" },
    { label: "Unknown", value: "unknown" },
  ],
  received_status: [
    { label: "Select…", value: "" },
    { label: "Received", value: "received" }, { label: "Not Received", value: "not_received" },
    { label: "Partial", value: "partial" }, { label: "NULL", value: "NULL" },
  ],
  paid_status: [
    { label: "Select…", value: "" },
    { label: "Paid", value: "paid" }, { label: "Not Paid", value: "not_paid" },
    { label: "Partial", value: "partial" }, { label: "NULL", value: "NULL" },
  ],
};

const READONLY_FIELDS = new Set(["raw_total_amount", "final_total_amount", "payable_amount"]);

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [stageMessage, setStageMessage] = useState("");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const [duplicateMessage, setDuplicateMessage] = useState("");
  const [existingDocumentId, setExistingDocumentId] = useState("");
  const [showAmountMismatch, setShowAmountMismatch] = useState(false);

  useEffect(() => { setLang(getStoredLanguage()); }, []);

  const t = ui[lang];

  const parseAmt = (v: string | number) => {
    const n = Number(String(v ?? "").replace(/,/g, "").replace(/Rs\.?/gi, "").trim());
    return Number.isFinite(n) ? n : 0;
  };

  const recalculate = (p: PreviewData): PreviewData => {
    const items = (p.items || []).map((item) => {
      const q = parseAmt(item.quantity), u = parseAmt(item.unit_price);
      return { ...item, line_total: q > 0 && u > 0 ? +(q * u).toFixed(2) : item.line_total };
    });
    const total = +(items.reduce((s, i) => s + parseAmt(i.line_total), 0)).toFixed(2);
    return { ...p, items, final_total_amount: total, payable_amount: total };
  };

  const resetForm = () => {
    setPreview(null); setSelectedFile(null); setSessionId("");
    setShowDuplicateWarning(false); setDuplicateMessage(""); setExistingDocumentId("");
    setShowAmountMismatch(false); setError(""); setActiveStep(0); setStageMessage("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleProcess = async () => {
    if (!selectedFile) return;
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    setIsProcessing(true); setError(""); setPreview(null);
    setActiveStep(1); setStageMessage("Preparing document…");

    try {
      const fd = new FormData();
      fd.append("file", selectedFile);
      const res = await fetch(`${BACKEND_URL}/process-document-stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });

      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { message?: string };
        throw new Error(err.message || `Server error ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let event: StreamEvent;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.stage === "error") throw new Error(event.message || "Processing failed.");
          if (typeof event.step === "number") setActiveStep(event.step);
          if (event.message) setStageMessage(event.message);
          if (event.stage === "done") {
            setPreview(event.preview ?? null);
            setSessionId(event.session_id ?? "");
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong during processing.");
      setActiveStep(0);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSave = async (force = false) => {
    if (!preview || !sessionId) return;
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    if (!force && parseAmt(preview.raw_total_amount) !== parseAmt(preview.final_total_amount)) {
      setShowAmountMismatch(true); return;
    }

    setIsSaving(true); setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, edited_preview: preview, force_save: force }),
      });
      if (res.status === 401) { localStorage.removeItem("token"); router.push("/login"); return; }
      const data = await res.json();

      if (data.duplicate_found && !data.success) {
        setShowDuplicateWarning(true);
        setDuplicateMessage(data.message || "Document already exists.");
        setExistingDocumentId(data.existing_document_id || "NULL");
        return;
      }

      if (!res.ok || !data.success) throw new Error(data.message || "Save failed.");

      setSuccessMessage(`Saved successfully. Document ID: ${data.document_id}`);
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong while saving.");
    } finally {
      setIsSaving(false);
    }
  };

  const pipelineSteps = [
    { title: t.pdfToPages,    desc: t.pdfToPagesDesc,                    step: 1 },
    { title: t.ocrExtraction, desc: t.ocrExtractionDesc,                 step: 2 },
    { title: t.textChunking,  desc: t.textChunkingDesc ?? "LLM correction & structuring", step: 3 },
    { title: t.vectorIndexing,desc: t.vectorIndexingDesc ?? "Field extraction & validation", step: 4 },
  ].map((s) => ({
    ...s,
    done:    activeStep > s.step || !!preview,
    current: isProcessing && activeStep === s.step,
    liveMsg: isProcessing && activeStep === s.step ? stageMessage : "",
  }));

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">

          {/* Top bar */}
          <div className="mb-5 flex items-center justify-between">
            <button
              onClick={() => router.push("/dashboard")}
              className="flex items-center gap-1.5 text-[13px] font-semibold transition hover:opacity-75"
              style={{ color: "var(--brand-mid)" }}
            >
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              {t.backToDashboard}
            </button>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </div>

          <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)] sm:text-[26px]">
            {t.uploadTitle}
          </h1>
          <p className="mt-1.5 text-[13px] leading-6 text-[var(--text-2)]">{t.uploadSubtitle}</p>

          <input
            ref={fileInputRef} type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] || null;
              setSelectedFile(f); setPreview(null); setError("");
              setSuccessMessage(""); setSessionId(""); setShowDuplicateWarning(false);
              setShowAmountMismatch(false);
            }}
          />

          {/* Drop zone */}
          <div
            className="mt-6 rounded-2xl p-8 text-center"
            style={{
              border: "2px dashed var(--brand-mid)",
              background: "var(--surface)",
              opacity: selectedFile ? 0.85 : 1,
            }}
          >
            <div
              className="mx-auto flex h-14 w-14 items-center justify-center rounded-full"
              style={{ background: "var(--brand-tint)" }}
            >
              <span className="material-symbols-outlined text-[28px]" style={{ color: "var(--brand-mid)" }}>
                {selectedFile
                  ? selectedFile.type.includes("pdf") ? "picture_as_pdf" : "image"
                  : "upload_file"}
              </span>
            </div>
            <h2 className="mt-4 text-[17px] font-bold text-[var(--text-1)]">
              {selectedFile ? selectedFile.name : t.dragDrop}
            </h2>
            <p className="mt-1 text-[13px] text-[var(--text-2)]">
              {selectedFile
                ? `${(selectedFile.size / 1024).toFixed(0)} KB · Ready for OCR`
                : t.maxFileSize}
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mt-5 rounded-xl px-6 py-2.5 text-[13px] font-semibold transition hover:opacity-80"
              style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
            >
              {selectedFile ? "Choose Another File" : t.selectDevice}
            </button>
          </div>

          {selectedFile && (
            <div className="mt-4 rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
                  <span className="material-symbols-outlined text-[22px]">
                    {selectedFile.type.includes("pdf") ? "picture_as_pdf" : "image"}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-semibold text-[var(--text-1)]">{selectedFile.name}</p>
                  <p className="text-[12px] text-[var(--text-3)]">
                    {(selectedFile.size / 1024).toFixed(0)} KB · OCR ready
                  </p>
                </div>
                <button onClick={resetForm} className="text-[var(--text-3)] transition hover:text-red-500">
                  <span className="material-symbols-outlined text-[22px]">close</span>
                </button>
              </div>
            </div>
          )}

          {/* Pipeline steps */}
          <div className="mt-8">
            <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--text-3)]">
              {t.processingPipeline}
            </p>
            <div className="space-y-4">
              {pipelineSteps.map((step, i) => (
                <div key={i} className="flex gap-4">
                  <div className="flex w-7 flex-col items-center">
                    <div
                      className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold transition-all"
                      style={
                        step.done
                          ? { background: "var(--brand)", color: "#fff" }
                          : step.current
                          ? { background: "var(--brand-mid)", color: "#fff", boxShadow: "0 0 0 3px var(--brand-tint)" }
                          : { border: "2px solid var(--border)", color: "var(--text-3)" }
                      }
                    >
                      {step.done ? "✓" : step.current ? (
                        <span style={{ fontSize: 13, lineHeight: 1 }}>⟳</span>
                      ) : i + 1}
                    </div>
                    {i < 3 && <div className="mt-1 h-full w-px" style={{ background: "var(--border)" }} />}
                  </div>
                  <div
                    className="flex-1 rounded-2xl p-4 transition-all"
                    style={{
                      background: "var(--surface)",
                      border: step.current
                        ? "1px solid var(--brand-mid)"
                        : "1px solid var(--border)",
                    }}
                  >
                    <p className="text-[14px] font-bold text-[var(--text-1)]">{step.title}</p>
                    <p className="mt-0.5 text-[12px] text-[var(--text-2)]">
                      {step.liveMsg || step.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="mt-5 rounded-xl px-4 py-3 text-[13px] text-red-600"
              style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)" }}>
              {error}
            </div>
          )}

          {successMessage && (
            <div className="mt-5 rounded-xl px-4 py-3 text-[13px] text-emerald-700"
              style={{ background: "rgba(22,163,74,0.08)", border: "1px solid rgba(22,163,74,0.2)" }}>
              {successMessage}
            </div>
          )}

          <button
            onClick={handleProcess}
            disabled={!selectedFile || isProcessing}
            className="mt-6 w-full rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-50"
            style={{ background: "var(--brand)" }}
          >
            {isProcessing
              ? stageMessage || "Processing…"
              : preview
              ? "Processing Done ✓"
              : t.startProcessing}
          </button>

          {/* Preview */}
          {preview && (
            <div className="mt-8 rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <h2 className="text-[19px] font-extrabold text-[var(--text-1)]">Extracted Preview</h2>
              <p className="mt-1 text-[13px] text-[var(--text-2)]">Review and edit before saving.</p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {FIELD_ROWS.map(([field, label]) => {
                  const opts = SELECT_OPTS[field];
                  const isReadonly = READONLY_FIELDS.has(field);
                  return (
                    <div key={field}>
                      <p className="mb-1.5 text-[12px] font-semibold text-[var(--text-2)]">{label}</p>
                      {opts ? (
                        <select
                          value={String((preview as Record<string, unknown>)[field] ?? "")}
                          onChange={(e) => setPreview({ ...preview, [field]: e.target.value })}
                          className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition"
                        >
                          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      ) : (
                        <input
                          value={String((preview as Record<string, unknown>)[field] ?? "")}
                          onChange={(e) => !isReadonly && setPreview({ ...preview, [field]: e.target.value })}
                          readOnly={isReadonly}
                          className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition"
                          style={isReadonly ? { background: "var(--input-bg-ro)", cursor: "not-allowed" } : {}}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Items */}
              {preview.items && preview.items.length > 0 && (
                <div className="mt-6">
                  <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">Items</p>
                  <div className="space-y-3">
                    {preview.items.map((item, idx) => (
                      <div key={idx} className="grid gap-3 rounded-xl p-4 sm:grid-cols-3"
                        style={{ border: "1px solid var(--border)", background: "var(--surface-2)" }}>
                        {(["description", "quantity", "unit_price"] as (keyof PreviewItem)[]).map((f) => (
                          <input
                            key={f}
                            value={String(item[f] ?? "")}
                            onChange={(e) => {
                              const items = [...preview.items];
                              items[idx] = { ...items[idx], [f]: e.target.value };
                              const next = { ...preview, items };
                              setPreview(f === "quantity" || f === "unit_price" ? recalculate(next) : next);
                            }}
                            placeholder={f.replace("_", " ")}
                            className="field-input rounded-xl border px-3 py-2 text-[13px] transition"
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Amount mismatch warning */}
              {showAmountMismatch && (
                <div className="mt-6 rounded-xl p-4 text-[13px]"
                  style={{ background: "rgba(217,119,6,0.08)", border: "1px solid rgba(217,119,6,0.3)", color: "#92400e" }}>
                  <p className="font-semibold">Raw and final totals differ.</p>
                  <p className="mt-1">Save using the recalculated final amount?</p>
                  <div className="mt-3 flex gap-3">
                    <button onClick={() => { setShowAmountMismatch(false); handleSave(true); }}
                      disabled={isSaving}
                      className="rounded-xl px-4 py-2 text-[13px] font-bold text-white"
                      style={{ background: "#d97706" }}>Save Anyway</button>
                    <button onClick={() => setShowAmountMismatch(false)}
                      className="rounded-xl px-4 py-2 text-[13px] font-semibold"
                      style={{ border: "1px solid rgba(217,119,6,0.4)", color: "#92400e" }}>Cancel</button>
                  </div>
                </div>
              )}

              {/* Duplicate warning */}
              {showDuplicateWarning && (
                <div className="mt-6 rounded-xl p-4 text-[13px]"
                  style={{ background: "rgba(217,119,6,0.08)", border: "1px solid rgba(217,119,6,0.3)", color: "#92400e" }}>
                  <p className="font-semibold">{duplicateMessage}</p>
                  <p className="mt-1">Existing ID: {existingDocumentId}</p>
                  <div className="mt-3 flex gap-3">
                    <button onClick={() => handleSave(true)} disabled={isSaving}
                      className="rounded-xl px-4 py-2 text-[13px] font-bold text-white" style={{ background: "#d97706" }}>
                      Save Anyway
                    </button>
                    <button onClick={() => { setShowDuplicateWarning(false); setDuplicateMessage(""); }}
                      className="rounded-xl px-4 py-2 text-[13px] font-semibold"
                      style={{ border: "1px solid rgba(217,119,6,0.4)", color: "#92400e" }}>Cancel</button>
                  </div>
                </div>
              )}

              <button
                onClick={() => handleSave(false)}
                disabled={isSaving}
                className="mt-6 w-full rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
                style={{ background: "#16a34a" }}
              >
                {isSaving ? "Saving…" : "Confirm and Save"}
              </button>
            </div>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}
