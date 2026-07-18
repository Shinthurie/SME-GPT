"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/layout/PageShell";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";
import { resolveBackendUrl } from "@/lib/backendUrl";

const BACKEND_URL = resolveBackendUrl();

// OCR runs automatically for every file; saving is always a manual step the
// user confirms per document, after reviewing the extracted preview.
type FileStatus = "pending" | "processing" | "ready" | "saving" | "done" | "error" | "skipped" | "cancelled";

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

type QueueItem = {
  id: string;
  file: File;
  status: FileStatus;
  message: string;
  sessionId?: string;
  preview?: PreviewData;
  expanded?: boolean;
  documentId?: string;
  documentType?: string;
  total?: string;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

const statusColors: Record<FileStatus, string> = {
  pending:    "var(--text-3)",
  processing: "var(--brand-mid)",
  ready:      "#0891b2",
  saving:     "var(--brand-mid)",
  done:       "#16a34a",
  error:      "#dc2626",
  skipped:    "#ea6c0a",
  cancelled:  "var(--text-3)",
};
const statusIcons: Record<FileStatus, string> = {
  pending:    "hourglass_empty",
  processing: "progress_activity",
  ready:      "fact_check",
  saving:     "progress_activity",
  done:       "check_circle",
  error:      "error",
  skipped:    "warning",
  cancelled:  "block",
};

// ── Field definitions (mirrors /upload page) ────────────────────────────────
const DOC_TYPE_OPTS = [
  { label: "Invoice", value: "invoice" }, { label: "Receipt", value: "receipt" },
  { label: "PO", value: "po" }, { label: "DN", value: "dn" }, { label: "Unknown", value: "unknown" },
];
const FLOW_TYPE_OPTS = [
  { label: "Payable", value: "payable" }, { label: "Receivable", value: "receivable" },
  { label: "Cash Inflow", value: "cash_inflow" }, { label: "Cash Outflow", value: "cash_outflow" },
];

function getSupplierLabel(docType: string, flowType: string): string {
  if (docType === "dn") return "Delivered By (Supplier)";
  if (docType === "po") return "Supplier";
  if (docType === "invoice") return ["receivable", "cash_inflow"].includes(flowType) ? "Bill To (Customer)" : "Bill From (Supplier)";
  if (docType === "receipt") return ["cash_inflow", "receivable"].includes(flowType) ? "Received From (Customer)" : "Paid To (Supplier)";
  return ["receivable", "cash_inflow"].includes(flowType) ? "Customer" : "Supplier";
}

function parseAmt(v: string | number): number {
  const n = Number(String(v ?? "").replace(/,/g, "").replace(/Rs\.?/gi, "").trim());
  return Number.isFinite(n) ? n : 0;
}

function recalcTotal(p: PreviewData): PreviewData {
  const items = (p.items || []).map((item) => {
    const q = parseAmt(item.quantity), u = parseAmt(item.unit_price);
    return { ...item, line_total: q > 0 && u > 0 ? +(q * u).toFixed(2) : item.line_total };
  });
  const total = +(items.reduce((s, i) => s + parseAmt(i.line_total), 0)).toFixed(2);
  return { ...p, items, final_total_amount: total, payable_amount: total };
}

function _writeBulkQueue(changedItem?: Partial<QueueItem> & { id?: string }) {
  // keep a lightweight widget-readable list in localStorage
  // called on status transitions so the floating widget stays current
  try {
    const existing = JSON.parse(localStorage.getItem("sme_bulk_queue") || "[]") as Array<{
      id: string; fileName: string; status: string; sessionId?: string;
    }>;
    if (changedItem?.id) {
      const idx = existing.findIndex((e) => e.id === changedItem.id);
      const entry = {
        id: changedItem.id,
        fileName: (changedItem as QueueItem).file?.name ?? "",
        status: changedItem.status ?? "pending",
        sessionId: changedItem.sessionId,
      };
      if (idx >= 0) existing[idx] = entry;
      else existing.push(entry);
    }
    localStorage.setItem("sme_bulk_queue", JSON.stringify(existing));
    window.dispatchEvent(new Event("sme-bulk-updated"));
  } catch { /* non-fatal */ }
}

export default function BulkUploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const controllers = useRef<Map<string, AbortController>>(new Map());

  useEffect(() => { setLang(getStoredLanguage()); }, []);
  const t = ui[lang];

  const addFiles = (files: FileList | null) => {
    if (!files) return;
    const items: QueueItem[] = Array.from(files).map((f) => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      status: "pending",
      message: lang === "si" ? "රැඳී සිටී..." : "Waiting...",
    }));
    setQueue((q) => [...q, ...items]);
    items.forEach((item) => _writeBulkQueue(item));
  };

  const updateItem = (id: string, patch: Partial<QueueItem>) =>
    setQueue((q) => q.map((item) => (item.id === id ? { ...item, ...patch } : item)));

  // ── Step 1: Run OCR only — stop at "ready" for the user to review ─────────
  const processOne = async (item: QueueItem): Promise<void> => {
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    const controller = new AbortController();
    controllers.current.set(item.id, controller);

    updateItem(item.id, { status: "processing", message: lang === "si" ? "OCR සකසමින්..." : "Running OCR..." });

    try {
      const fd = new FormData();
      fd.append("file", item.file);

      const res = await fetch(`${BACKEND_URL}/process-document-stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
        signal: controller.signal,
      });

      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let sessionId = "";
      let preview: PreviewData | null = null;

      updateItem(item.id, { message: lang === "si" ? "OCR කියවමින්..." : "Reading OCR..." });

      while (true) {
        if (controller.signal.aborted) throw new DOMException("Cancelled", "AbortError");
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.stage === "error") throw new Error(event.message || "Processing failed");
            if (event.stage === "done") {
              sessionId = event.session_id ?? "";
              preview = event.preview ?? null;
            }
            if (event.message) updateItem(item.id, { message: event.message });
          } catch { /* ignore parse errors */ }
        }
      }

      if (!sessionId || !preview) throw new Error("No session from OCR");

      // Store preview in sessionStorage for the bulk-review page
      sessionStorage.setItem(`sme_bulk_${sessionId}`, JSON.stringify({
        preview,
        fileName: item.file.name,
        arithmeticStatus: preview ? "unknown" : "unknown",
      }));

      // Update localStorage widget queue
      _writeBulkQueue({ ...item, status: "ready", sessionId, preview });

      // Stop here — wait for the user to review and explicitly save
      updateItem(item.id, {
        status: "ready",
        sessionId,
        preview,
        expanded: true,
        message: lang === "si" ? "සමාලෝචනය සඳහා සූදානම්" : "Ready for review",
      });

    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        updateItem(item.id, { status: "cancelled", message: lang === "si" ? "අවලංගු කරන ලදී" : "Cancelled" });
        _writeBulkQueue({ ...item, status: "cancelled" });
      } else {
        updateItem(item.id, { status: "error", message: err instanceof Error ? err.message : "Failed" });
        _writeBulkQueue({ ...item, status: "error" });
      }
    } finally {
      controllers.current.delete(item.id);
    }
  };

  const runAll = async () => {
    if (running) return;
    setRunning(true);
    setDone(false);
    const pending = queue.filter((i) => i.status === "pending");
    for (const item of pending) {
      await processOne(item);
    }
    setRunning(false);
    setDone(true);
  };

  // ── Step 2: User edits the preview inline ──────────────────────────────────
  const updatePreviewField = (id: string, key: keyof PreviewData, value: string) => {
    setQueue((q) => q.map((item) => {
      if (item.id !== id || !item.preview) return item;
      return { ...item, preview: { ...item.preview, [key]: value } };
    }));
  };

  const updatePreviewItem = (id: string, idx: number, key: keyof PreviewItem, value: string) => {
    setQueue((q) => q.map((item) => {
      if (item.id !== id || !item.preview) return item;
      const items = item.preview.items.map((it, i) => i === idx ? { ...it, [key]: value } : it);
      return { ...item, preview: recalcTotal({ ...item.preview, items }) };
    }));
  };

  const toggleExpand = (id: string) =>
    setQueue((q) => q.map((item) => item.id === id ? { ...item, expanded: !item.expanded } : item));

  // ── Step 3: User clicks Save — only now does the document get persisted ───
  const saveItem = async (item: QueueItem) => {
    if (!item.sessionId || !item.preview) return;
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    updateItem(item.id, { status: "saving", message: lang === "si" ? "සුරකිමින්..." : "Saving..." });

    try {
      const saveRes = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: item.sessionId, edited_preview: item.preview, force_save: false }),
      });
      const saveData = await saveRes.json();

      if (saveData.duplicate_found && !saveData.success) {
        updateItem(item.id, {
          status: "skipped",
          message: `${lang === "si" ? "දැනටමත් ඇත:" : "Duplicate:"} ${saveData.existing_document_id || ""}`,
        });
        return;
      }
      if (!saveRes.ok || !saveData.success) throw new Error(saveData.message || "Save failed");

      const doneUpdate: Partial<QueueItem> = {
        status: "done",
        documentId: saveData.document_id,
        documentType: String(item.preview.document_type || ""),
        total: String(item.preview.final_total_amount || ""),
        expanded: false,
        message: `${lang === "si" ? "සුරකිනු ලැබිණි:" : "Saved:"} ${saveData.document_id}`,
      };
      updateItem(item.id, doneUpdate);
      _writeBulkQueue({ ...item, ...doneUpdate });

      addNotification({
        type: "success",
        title: lang === "si" ? "ලේඛනය සුරකිනු ලැබිණි" : "Document Saved",
        message: `${saveData.document_id} — ${item.file.name}`,
      });
    } catch (err) {
      updateItem(item.id, { status: "error", message: err instanceof Error ? err.message : "Save failed" });
    }
  };

  const cancelItem = (id: string) => {
    const controller = controllers.current.get(id);
    if (controller) controller.abort();
  };

  const removeItem = (id: string) => {
    cancelItem(id);
    setQueue((q) => q.filter((i) => i.id !== id));
  };
  const clearDone = () => setQueue((q) => q.filter((i) => !["done", "skipped", "cancelled"].includes(i.status)));

  const counts = {
    pending:    queue.filter((i) => i.status === "pending").length,
    processing: queue.filter((i) => i.status === "processing").length,
    ready:      queue.filter((i) => i.status === "ready").length,
    done:       queue.filter((i) => i.status === "done").length,
    error:      queue.filter((i) => i.status === "error").length,
    skipped:    queue.filter((i) => i.status === "skipped").length,
    cancelled:  queue.filter((i) => i.status === "cancelled").length,
  };

  return (
    <PageShell
      backLabel={t.backToDashboard}
      title={lang === "si" ? "ශ්‍රේණිගත ලේඛන උඩුගත කිරීම" : "Bulk Document Upload"}
      subtitle={lang === "si"
        ? "ගොනු කිහිපයක් එකවර උඩුගත කරන්න — OCR ස්වයංක්‍රීයව සිදුවේ, සුරැකීම ඔබ අනුමත කළ පසු පමණි."
        : "Upload multiple files at once — OCR runs automatically, but each document is only saved after you review and confirm it."}
      width="standard"
    >

          {/* Drop zone */}
          <div
            className="mt-6 cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition hover:border-[var(--brand-mid)]"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            onClick={() => fileInputRef.current?.click()}
            onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
            onDragOver={(e) => e.preventDefault()}
          >
            <span className="material-symbols-outlined text-[40px]" style={{ color: "var(--brand-mid)" }}>upload_file</span>
            <p className="mt-2 text-[15px] font-semibold text-[var(--text-1)]">
              {lang === "si" ? "ගොනු ඇදගෙන දමන්න හෝ ක්ලික් කරන්න" : "Drag & drop files or click to select"}
            </p>
            <p className="mt-1 text-[12px] text-[var(--text-3)]">PDF, PNG, JPG, WEBP — multiple files</p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {/* Stats bar */}
          {queue.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl px-5 py-3"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              {[
                { label: lang === "si" ? "රැඳී" : "Pending",      count: counts.pending,    color: "var(--text-3)" },
                { label: lang === "si" ? "සකසමින්" : "Processing", count: counts.processing, color: "var(--brand-mid)" },
                { label: lang === "si" ? "සමාලෝචනය" : "Ready to review", count: counts.ready, color: "#0891b2" },
                { label: lang === "si" ? "සුරකිනු" : "Done",      count: counts.done,       color: "#16a34a" },
                { label: lang === "si" ? "දෝෂ" : "Errors",        count: counts.error,      color: "#dc2626" },
                { label: lang === "si" ? "හමු" : "Skipped",       count: counts.skipped,    color: "#ea6c0a" },
                { label: lang === "si" ? "අවලංගු" : "Cancelled",  count: counts.cancelled,  color: "var(--text-3)" },
              ].map(({ label, count, color }) => count > 0 && (
                <span key={label} className="text-[12px] font-bold" style={{ color }}>
                  {count} {label}
                </span>
              ))}
              <div className="ml-auto flex gap-2">
                {counts.done + counts.skipped + counts.cancelled > 0 && (
                  <button onClick={clearDone}
                    className="rounded-xl px-3 py-1.5 text-[11px] font-semibold transition hover:opacity-80"
                    style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}>
                    {lang === "si" ? "සම්පූර්ණ ඉවත් කරන්න" : "Clear done"}
                  </button>
                )}
                <button
                  onClick={runAll}
                  disabled={running || counts.pending === 0}
                  className="flex items-center gap-2 rounded-xl px-4 py-1.5 text-[12px] font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                  style={{ background: "var(--brand)" }}
                >
                  {running
                    ? <><span className="material-symbols-outlined animate-spin text-[14px]">progress_activity</span>{lang === "si" ? "සකසමින්..." : "Processing..."}</>
                    : <><span className="material-symbols-outlined text-[14px]">play_arrow</span>{lang === "si" ? "සියල්ල ආරම්භ කරන්න" : `Run OCR on ${counts.pending}`}</>}
                </button>
              </div>
            </div>
          )}

          {/* Queue list */}
          {queue.length > 0 && (
            <div className="mt-4 space-y-2">
              {queue.map((item) => (
                <div key={item.id} className="rounded-2xl overflow-hidden"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>

                  {/* Row header */}
                  <div className="flex items-center gap-4 px-4 py-3">
                    <span
                      className={`material-symbols-outlined text-[22px] ${item.status === "processing" || item.status === "saving" ? "animate-spin" : ""}`}
                      style={{ color: statusColors[item.status] }}>
                      {statusIcons[item.status]}
                    </span>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-semibold text-[var(--text-1)]">{item.file.name}</p>
                      <p className="text-[11px]" style={{ color: statusColors[item.status] }}>{item.message}</p>
                    </div>

                    {item.status === "done" && item.documentId && (
                      <div className="text-right">
                        <p className="text-[11px] font-bold uppercase text-[var(--text-3)]">{item.documentType}</p>
                        {item.total && item.total !== "NULL" && (
                          <p className="text-[12px] font-bold" style={{ color: "#16a34a" }}>LKR {item.total}</p>
                        )}
                      </div>
                    )}

                    <div className="flex gap-2">
                      {item.status === "pending" && (
                        <button onClick={() => processOne(item)}
                          className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-bold transition hover:opacity-80"
                          style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
                          <span className="material-symbols-outlined text-[13px]">play_arrow</span>
                          {lang === "si" ? "ක‍‍‍ි‍රියාත්මක" : "Process"}
                        </button>
                      )}
                      {item.status === "ready" && item.sessionId && (
                        <button onClick={() => router.push(`/bulk-review/${item.sessionId}`)}
                          className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-bold transition hover:opacity-80"
                          style={{ background: "rgba(8,145,178,0.12)", color: "#0891b2" }}>
                          <span className="material-symbols-outlined text-[13px]">open_in_new</span>
                          {lang === "si" ? "සමාලෝචනය" : "Review & Save"}
                        </button>
                      )}
                      {item.status === "done" && item.documentId && (
                        <button onClick={() => router.push(`/analysis/${item.documentId}`)}
                          className="rounded-lg px-2 py-1 text-[10px] font-bold transition hover:opacity-80"
                          style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
                          {lang === "si" ? "විවෘත" : "Open"}
                        </button>
                      )}
                      {(item.status === "processing" || item.status === "ready") && (
                        <button onClick={() => cancelItem(item.id)}
                          className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-bold transition hover:opacity-80"
                          style={{ background: "rgba(220,38,38,0.08)", color: "#dc2626" }}>
                          <span className="material-symbols-outlined text-[13px]">cancel</span>
                          {lang === "si" ? "අවලංගු" : "Cancel"}
                        </button>
                      )}
                      {item.status !== "processing" && item.status !== "saving" && (
                        <button onClick={() => removeItem(item.id)}
                          className="text-[var(--text-3)] transition hover:text-red-500">
                          <span className="material-symbols-outlined text-[16px]">close</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Inline review panel — only when ready + expanded */}
                  {item.status === "ready" && item.expanded && item.preview && (
                    <div className="border-t px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">Document Type</label>
                          <select value={item.preview.document_type}
                            onChange={(e) => updatePreviewField(item.id, "document_type", e.target.value)}
                            className="w-full rounded-lg border px-3 py-2 text-[13px]"
                            style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }}>
                            {DOC_TYPE_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                        </div>
                        {item.preview.document_type !== "dn" && item.preview.document_type !== "po" && (
                          <div>
                            <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">Flow Type</label>
                            <select value={item.preview.flow_type}
                              onChange={(e) => updatePreviewField(item.id, "flow_type", e.target.value)}
                              className="w-full rounded-lg border px-3 py-2 text-[13px]"
                              style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }}>
                              {FLOW_TYPE_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          </div>
                        )}
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">
                            {getSupplierLabel(item.preview.document_type, item.preview.flow_type)}
                          </label>
                          <input value={item.preview.supplier_name}
                            onChange={(e) => updatePreviewField(item.id, "supplier_name", e.target.value)}
                            className="w-full rounded-lg border px-3 py-2 text-[13px]"
                            style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                        </div>
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">Date</label>
                          <input value={item.preview.date}
                            onChange={(e) => updatePreviewField(item.id, "date", e.target.value)}
                            className="w-full rounded-lg border px-3 py-2 text-[13px]"
                            style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                        </div>
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">Currency</label>
                          <input value={item.preview.currency}
                            onChange={(e) => updatePreviewField(item.id, "currency", e.target.value)}
                            className="w-full rounded-lg border px-3 py-2 text-[13px]"
                            style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                        </div>
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-[var(--text-3)]">Final Total</label>
                          <input value={String(item.preview.final_total_amount ?? "")}
                            onChange={(e) => updatePreviewField(item.id, "final_total_amount", e.target.value)}
                            className="w-full rounded-lg border px-3 py-2 text-[13px] font-bold"
                            style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                        </div>
                      </div>

                      {/* Items table */}
                      {item.preview.items && item.preview.items.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-[11px] font-bold uppercase text-[var(--text-3)]">Items</p>
                          {item.preview.items.map((it, idx) => (
                            <div key={idx} className="grid grid-cols-[1fr_70px_90px_90px] gap-2">
                              <input value={String(it.description)}
                                onChange={(e) => updatePreviewItem(item.id, idx, "description", e.target.value)}
                                placeholder={t.description}
                                className="rounded-lg border px-2 py-1.5 text-[12px]"
                                style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                              <input value={String(it.quantity)}
                                onChange={(e) => updatePreviewItem(item.id, idx, "quantity", e.target.value)}
                                placeholder={t.quantity}
                                className="rounded-lg border px-2 py-1.5 text-[12px] text-right"
                                style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                              <input value={String(it.unit_price)}
                                onChange={(e) => updatePreviewItem(item.id, idx, "unit_price", e.target.value)}
                                placeholder={t.unitPrice}
                                className="rounded-lg border px-2 py-1.5 text-[12px] text-right"
                                style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                              <input value={String(it.line_total)} readOnly
                                className="rounded-lg border px-2 py-1.5 text-[12px] text-right font-semibold"
                                style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-2)" }} />
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="mt-4 flex justify-end gap-2">
                        <button onClick={() => toggleExpand(item.id)}
                          className="rounded-xl px-4 py-2 text-[12px] font-semibold transition hover:opacity-80"
                          style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}>
                          {lang === "si" ? "පසුව" : "Later"}
                        </button>
                        <button onClick={() => saveItem(item)}
                          className="flex items-center gap-2 rounded-xl px-5 py-2 text-[12px] font-bold text-white transition hover:opacity-90"
                          style={{ background: "#16a34a" }}>
                          <span className="material-symbols-outlined text-[15px]">save</span>
                          {lang === "si" ? "සුරකින්න" : "Save Document"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {queue.length === 0 && (
            <div className="mt-8 rounded-2xl px-4 py-10 text-center text-[14px] text-[var(--text-2)]"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <span className="material-symbols-outlined text-[36px] text-[var(--text-3)]">folder_open</span>
              <p className="mt-2">{lang === "si" ? "ගොනු තෝරන්නෙකු ඉහත ක්ලික් කරන්න" : "Select files above to get started"}</p>
            </div>
          )}

          {/* Success summary */}
          {done && counts.pending === 0 && counts.processing === 0 && counts.ready === 0 && (
            <div className="mt-4 rounded-2xl px-5 py-4 text-[13px]"
              style={{ background: "rgba(22,163,74,0.06)", border: "1px solid rgba(22,163,74,0.2)", color: "#16a34a" }}>
              <span className="material-symbols-outlined text-[18px] align-bottom mr-2">check_circle</span>
              {lang === "si"
                ? `${counts.done} ලේඛන සාර්ථකව සුරකිනු ලැබිණි. ${counts.error ? `${counts.error} අසාර්ථකයි.` : ""} ${counts.skipped ? `${counts.skipped} දෙකක් ඇත.` : ""}`
                : `${counts.done} document${counts.done !== 1 ? "s" : ""} saved.${counts.error ? ` ${counts.error} failed.` : ""}${counts.skipped ? ` ${counts.skipped} duplicate${counts.skipped !== 1 ? "s" : ""} skipped.` : ""}`}
              <button onClick={() => router.push("/repository")}
                className="ml-3 font-bold underline transition hover:opacity-75">
                {lang === "si" ? "ගබඩාව බලන්න" : "View repository"}
              </button>
            </div>
          )}

    </PageShell>
  );
}
