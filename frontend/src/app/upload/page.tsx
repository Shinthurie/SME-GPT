"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";

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

// ── Field definitions per document type ─────────────────────────────────────

const DOC_TYPE_OPTS = [
  { label: "Select…", value: "" },
  { label: "Invoice",  value: "invoice"  },
  { label: "Receipt",  value: "receipt"  },
  { label: "PO",       value: "po"       },
  { label: "DN",       value: "dn"       },
  { label: "Unknown",  value: "unknown"  },
];

const FLOW_TYPE_OPTS = [
  { label: "Select…",      value: "" },
  { label: "Payable",      value: "payable"      },
  { label: "Receivable",   value: "receivable"   },
  { label: "Cash Inflow",  value: "cash_inflow"  },
  { label: "Cash Outflow", value: "cash_outflow" },
];

const RECEIVED_STATUS_OPTS = [
  { label: "Select…",      value: "" },
  { label: "Received",     value: "received"     },
  { label: "Not Received", value: "not_received" },
  { label: "Partial",      value: "partial"      },
  { label: "NULL",         value: "NULL"         },
];

const DELIVERY_STATUS_OPTS = [
  { label: "Select…",       value: "" },
  { label: "Delivered",     value: "delivered"     },
  { label: "Not Delivered", value: "not_delivered" },
  { label: "Partial",       value: "partial"       },
];

const PAID_STATUS_OPTS = [
  { label: "Select…",  value: "" },
  { label: "Paid",     value: "paid"     },
  { label: "Not Paid", value: "not_paid" },
  { label: "Partial",  value: "partial"  },
  { label: "NULL",     value: "NULL"     },
];

const PO_STATUS_OPTS = [
  { label: "Select…",   value: "" },
  { label: "Pending",   value: "not_paid"  },
  { label: "Approved",  value: "partial"   },
  { label: "Fulfilled", value: "paid"      },
  { label: "Cancelled", value: "NULL"      },
];

type FieldRow = { key: string; label: string; opts?: { label: string; value: string }[]; readonly?: boolean };

function getFieldRows(docType: string): FieldRow[] {
  if (docType === "dn") return [
    { key: "document_type", label: "Document Type",    opts: DOC_TYPE_OPTS },
    { key: "order_id",      label: "PO Reference"  },
    { key: "company_name",  label: "Received By (Your Company)" },
    { key: "supplier_name", label: "Delivered By"  },
    { key: "date",          label: "Delivery Date" },
    { key: "received_status", label: "Delivery Status", opts: DELIVERY_STATUS_OPTS },
  ];
  if (docType === "po") return [
    { key: "document_type",       label: "Document Type",   opts: DOC_TYPE_OPTS },
    { key: "order_id",            label: "PO Number"        },
    { key: "company_name",        label: "Ordered By (Your Company)" },
    { key: "supplier_name",       label: "Supplier"         },
    { key: "date",                label: "Order Date"       },
    { key: "currency",            label: "Currency"         },
    { key: "final_total_amount",  label: "Order Total", readonly: true },
    { key: "paid_status",         label: "PO Status",   opts: PO_STATUS_OPTS },
  ];
  // invoice / receipt / unknown — full form
  return [
    { key: "document_type",      label: "Document Type",      opts: DOC_TYPE_OPTS },
    { key: "order_id",           label: "Order ID"            },
    { key: "flow_type",          label: "Flow Type",          opts: FLOW_TYPE_OPTS },
    { key: "company_name",       label: "Company Name"        },
    { key: "supplier_name",      label: "Customer / Supplier" },
    { key: "date",               label: "Date"                },
    { key: "currency",           label: "Currency"            },
    { key: "raw_total_amount",   label: "Raw Total (OCR)",    readonly: true },
    { key: "final_total_amount", label: "Final Total",        readonly: true },
    { key: "payable_amount",     label: "Payable / Receivable", readonly: true },
    { key: "cash_return",        label: "Cash Return"         },
    { key: "received_status",    label: "Received Status",    opts: RECEIVED_STATUS_OPTS },
    { key: "paid_status",        label: "Paid Status",        opts: PAID_STATUS_OPTS },
  ];
}

function getItemFields(docType: string): ("description" | "quantity" | "unit_price")[] {
  // DN: only description + qty; everything else gets all three
  return docType === "dn" ? ["description", "quantity"] : ["description", "quantity", "unit_price"];
}

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewRef  = useRef<HTMLDivElement | null>(null);
  const videoRef    = useRef<HTMLVideoElement | null>(null);
  const canvasRef   = useRef<HTMLCanvasElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [ocrLang, setOcrLang] = useState<"en" | "si">("en");
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
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);

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

  // ── Camera helpers ───────────────────────────────────────────────────────
  const openCamera = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      setCameraStream(stream);
      setShowCamera(true);
      // Attach stream to video element after the modal renders
      setTimeout(() => {
        if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); }
      }, 100);
    } catch {
      setError("Camera access denied. Please allow camera permission and try again.");
    }
  };

  const closeCamera = () => {
    cameraStream?.getTracks().forEach(t => t.stop());
    setCameraStream(null);
    setShowCamera(false);
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      if (!blob) return;
      const file = new File([blob], `photo_${Date.now()}.jpg`, { type: "image/jpeg" });
      setSelectedFile(file);
      setPreview(null); setError(""); setSessionId("");
      closeCamera();
    }, "image/jpeg", 0.92);
  };

  const handleProcess = async () => {
    if (!selectedFile) return;
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    setIsProcessing(true); setError(""); setPreview(null);
    setActiveStep(1); setStageMessage("Preparing document…");

    addNotification({
      title: lang === "si" ? "ලේඛනය සකසමින් ඇත" : "Processing Document",
      message: lang === "si"
        ? `${selectedFile.name} — OCR සහ ක්ෂේත්‍ර ලබාගැනීම ආරම්භ විය.`
        : `${selectedFile.name} — OCR extraction started.`,
      type: "info",
    });

    try {
      const fd = new FormData();
      fd.append("file", selectedFile);
      fd.append("ocr_language", ocrLang);
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
    const controller = new AbortController();
    const saveTimeout = setTimeout(() => controller.abort(), 60_000);
    try {
      const res = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, edited_preview: preview, force_save: force }),
        signal: controller.signal,
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

      // Fire notification so the bell icon lights up
      const docId = data.document_id ?? "";
      addNotification({
        title: lang === "si" ? "ලේඛනය සාර්ථකව සුරකිනු ලැබිණි" : "Document Saved",
        message: lang === "si"
          ? `${docId} — OCR සහ ක්ෂේත්‍ර ලබාගැනීම සම්පූර්ණ විය. ලේඛනය ගබඩාවට එකතු කෙරිණි.`
          : `${docId} — OCR extraction complete. Document added to your repository.`,
        type: "success",
      });

      resetForm();
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setError("Save timed out after 60 s. Please check your connection and try again.");
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong while saving.");
      }
    } finally {
      clearTimeout(saveTimeout);
      setIsSaving(false);
    }
  };

  const pipelineSteps = [
    {
      title: t.pdfToPages ?? "PDF to Pages",
      desc:  t.pdfToPagesDesc ?? "Structure analysis & layout parsing",
      step: 1,
    },
    {
      title: t.ocrExtraction,
      desc:  t.ocrExtractionDesc,
      step: 2,
    },
  ].map((s) => ({
    ...s,
    done:    s.step === 1 ? (activeStep > 1 || !!preview) : !!preview,
    current: isProcessing && (s.step === 1 ? activeStep === 1 : activeStep >= 2),
    liveMsg: isProcessing && (s.step === 1 ? activeStep === 1 : activeStep >= 2) ? stageMessage : "",
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

          {/* OCR Language Engine selector */}
          <div className="mt-5">
            <div className="mb-2 flex items-center gap-2">
              <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--text-3)]">
                OCR Language Engine
              </p>
              <span
                title="English: best for typed/printed documents. Sinhala: best for Sinhala-primary or handwritten content. The engine always processes both scripts — this hint optimises the correction step."
                className="flex h-4 w-4 cursor-help items-center justify-center rounded-full text-[10px] font-bold"
                style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
              >
                ?
              </span>
            </div>
            <div className="flex gap-2">
              {(["en", "si"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setOcrLang(l)}
                  className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-semibold transition"
                  style={
                    ocrLang === l
                      ? { background: "var(--brand)", color: "#fff", boxShadow: "0 2px 8px var(--brand-ring)" }
                      : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }
                  }
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {l === "en" ? "language" : "translate"}
                  </span>
                  {l === "en" ? t.english : t.sinhala}
                </button>
              ))}
            </div>
          </div>

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
            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="rounded-xl px-5 py-2.5 text-[13px] font-semibold transition hover:opacity-80"
                style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
              >
                {selectedFile ? t.chooseAnother : t.selectDevice}
              </button>
              <button
                onClick={openCamera}
                className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-semibold transition hover:opacity-80"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}
              >
                <span className="material-symbols-outlined text-[17px]">photo_camera</span>
                {t.takePhoto}
              </button>
            </div>
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
                    {i < 1 && <div className="mt-1 h-full w-px" style={{ background: "var(--border)" }} />}
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

          {/* Enterprise Security banner */}
          <div
            className="mt-5 flex items-center gap-3 rounded-xl px-4 py-3"
            style={{ background: "rgba(26,53,96,0.06)", border: "1px solid rgba(26,53,96,0.12)" }}
          >
            <span className="material-symbols-outlined text-[18px]" style={{ color: "var(--brand)" }}>
              shield
            </span>
            <p className="text-[12px] text-[var(--text-2)]">
              <span className="font-bold" style={{ color: "var(--brand)" }}>
                {lang === "si" ? "ව්‍යාපාරික ආරක්ෂාව:" : "Enterprise Security:"}
              </span>{" "}
              {t.securityBanner}
            </p>
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
            onClick={
              preview
                ? () => previewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
                : handleProcess
            }
            disabled={!selectedFile || isProcessing}
            className="mt-6 w-full rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-50"
            style={{ background: preview ? "#16a34a" : "var(--brand)" }}
          >
            {isProcessing
              ? stageMessage || "Processing…"
              : preview
              ? t.extractionDone
              : t.beginExtraction}
          </button>

          {/* Preview */}
          {preview && (
            <div ref={previewRef} className="mt-8 rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <h2 className="text-[19px] font-extrabold text-[var(--text-1)]">{t.extractedPreview}</h2>
              <p className="mt-1 text-[13px] text-[var(--text-2)]">{t.reviewBeforeSaving}</p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {getFieldRows(String(preview.document_type || "")).map((row) => {
                  const val = String((preview as Record<string, unknown>)[row.key] ?? "");
                  return (
                    <div key={row.key}>
                      <p className="mb-1.5 text-[12px] font-semibold text-[var(--text-2)]">{row.label}</p>
                      {row.opts ? (
                        <select
                          value={val}
                          onChange={(e) => {
                            const next = { ...preview, [row.key]: e.target.value };
                            // Auto-set flow_type when document_type changes
                            if (row.key === "document_type") {
                              if (e.target.value === "dn")  next.flow_type = "expense";
                              if (e.target.value === "po")  next.flow_type = "payable";
                            }
                            setPreview(next);
                          }}
                          className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition"
                        >
                          {row.opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      ) : (
                        <input
                          value={val}
                          onChange={(e) => !row.readonly && setPreview({ ...preview, [row.key]: e.target.value })}
                          readOnly={row.readonly}
                          className="field-input w-full rounded-xl border px-4 py-2.5 text-[14px] transition"
                          style={row.readonly ? { background: "var(--input-bg-ro)", cursor: "not-allowed" } : {}}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Items */}
              {preview.items && preview.items.length > 0 && (
                <div className="mt-6">
                  <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">{t.itemsLabel}</p>
                  <div className="space-y-3">
                    {preview.items.map((item, idx) => (
                      <div key={idx} className="grid gap-3 rounded-xl p-4 sm:grid-cols-3"
                        style={{ border: "1px solid var(--border)", background: "var(--surface-2)" }}>
                        {(getItemFields(String(preview.document_type || "")) as (keyof PreviewItem)[]).map((f) => (
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
                      style={{ background: "#d97706" }}>{t.saveAnyway}</button>
                    <button onClick={() => setShowAmountMismatch(false)}
                      className="rounded-xl px-4 py-2 text-[13px] font-semibold"
                      style={{ border: "1px solid rgba(217,119,6,0.4)", color: "#92400e" }}>{t.cancel}</button>
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
                      style={{ border: "1px solid rgba(217,119,6,0.4)", color: "#92400e" }}>{t.cancel}</button>
                  </div>
                </div>
              )}

              <button
                onClick={() => handleSave(false)}
                disabled={isSaving}
                className="mt-6 w-full rounded-2xl py-4 text-[15px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
                style={{ background: "#16a34a" }}
              >
                {isSaving ? t.saving : t.confirmAndSave}
              </button>
            </div>
          )}
        </main>

        <BottomNav />

        {/* Hidden canvas for photo capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Camera modal */}
        {showCamera && (
          <div
            className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black"
            style={{ background: "rgba(0,0,0,0.95)" }}
          >
            <div className="relative w-full max-w-[640px]">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3">
                <p className="text-[15px] font-bold text-white">
                  {lang === "si" ? "ලේඛනය ඡායාරූප ගන්න" : "Take a photo of your document"}
                </p>
                <button onClick={closeCamera} className="text-white/70 hover:text-white">
                  <span className="material-symbols-outlined text-[26px]">close</span>
                </button>
              </div>

              {/* Viewfinder */}
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full rounded-xl"
                style={{ maxHeight: "65vh", objectFit: "cover", background: "#111" }}
              />

              {/* Guide overlay */}
              <div
                className="pointer-events-none absolute inset-0 m-auto rounded-xl"
                style={{
                  width: "90%", height: "70%",
                  top: "15%", left: "5%",
                  border: "2px solid rgba(255,255,255,0.5)",
                  borderRadius: "8px",
                }}
              />

              {/* Capture button */}
              <div className="flex items-center justify-center gap-6 py-6">
                <button
                  onClick={closeCamera}
                  className="rounded-full px-5 py-2 text-[13px] font-semibold text-white/70 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={capturePhoto}
                  className="flex h-16 w-16 items-center justify-center rounded-full bg-white shadow-lg transition hover:scale-105 active:scale-95"
                >
                  <span className="material-symbols-outlined text-[32px]" style={{ color: "var(--brand)" }}>
                    photo_camera
                  </span>
                </button>
                <div className="w-20" />
              </div>

              <p className="pb-4 text-center text-[12px] text-white/50">
                {lang === "si" ? "ලේඛනය රාමුව තුළ ස්ථාන කර ශූල් ඔබන්න" : "Place the document inside the frame then tap the button"}
              </p>
            </div>
          </div>
        )}
      </div>
    </MobileShell>
  );
}
