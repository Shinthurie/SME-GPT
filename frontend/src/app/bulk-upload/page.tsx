"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/layout/PageShell";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { addNotification } from "@/lib/notifications";

const BACKEND_URL = "http://127.0.0.1:8000";

type FileStatus = "pending" | "processing" | "done" | "error" | "skipped";

type QueueItem = {
  id: string;
  file: File;
  status: FileStatus;
  message: string;
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
  done:       "#16a34a",
  error:      "#dc2626",
  skipped:    "#ea6c0a",
};
const statusIcons: Record<FileStatus, string> = {
  pending:    "hourglass_empty",
  processing: "progress_activity",
  done:       "check_circle",
  error:      "error",
  skipped:    "warning",
};

export default function BulkUploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

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
  };

  const updateItem = (id: string, patch: Partial<QueueItem>) =>
    setQueue((q) => q.map((item) => (item.id === id ? { ...item, ...patch } : item)));

  const processOne = async (item: QueueItem): Promise<void> => {
    const token = getAuthToken();
    if (!token) { router.push("/login"); return; }

    updateItem(item.id, { status: "processing", message: lang === "si" ? "OCR සකසමින්..." : "Running OCR..." });

    try {
      // Step 1: stream process
      const fd = new FormData();
      fd.append("file", item.file);

      const res = await fetch(`${BACKEND_URL}/process-document-stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });

      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let sessionId = "";
      let preview: Record<string, unknown> | null = null;

      updateItem(item.id, { message: lang === "si" ? "OCR කියවමින්..." : "Reading OCR..." });

      while (true) {
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

      // Step 2: auto-confirm save (no manual review in bulk mode)
      updateItem(item.id, { message: lang === "si" ? "සුරකිමින්..." : "Saving..." });

      const saveRes = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, edited_preview: preview, force_save: false }),
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

      updateItem(item.id, {
        status: "done",
        documentId: saveData.document_id,
        documentType: String((preview as Record<string,unknown>).document_type || ""),
        total: String((preview as Record<string,unknown>).final_total_amount || ""),
        message: `${lang === "si" ? "සුරකිනු ලැබිණි:" : "Saved:"} ${saveData.document_id}`,
      });

      addNotification({
        type: "success",
        title: lang === "si" ? "ලේඛනය සුරකිනු ලැබිණි" : "Document Saved",
        message: `${saveData.document_id} — ${item.file.name}`,
      });

    } catch (err) {
      updateItem(item.id, {
        status: "error",
        message: err instanceof Error ? err.message : "Failed",
      });
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

  const removeItem = (id: string) => setQueue((q) => q.filter((i) => i.id !== id));
  const clearDone = () => setQueue((q) => q.filter((i) => i.status === "pending" || i.status === "error"));

  const counts = {
    pending:    queue.filter((i) => i.status === "pending").length,
    processing: queue.filter((i) => i.status === "processing").length,
    done:       queue.filter((i) => i.status === "done").length,
    error:      queue.filter((i) => i.status === "error").length,
    skipped:    queue.filter((i) => i.status === "skipped").length,
  };

  return (
    <PageShell
      backLabel={t.backToDashboard}
      title={lang === "si" ? "ශ්‍රේණිගත ලේඛන උඩුගත කිරීම" : "Bulk Document Upload"}
      subtitle={lang === "si" ? "ගොනු කිහිපයක් එකවර උඩුගත කර OCR ස්වයංක්‍රීයව කරන්න." : "Upload multiple files at once — OCR and save happen automatically for each."}
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
                { label: lang === "si" ? "රැඳී" : "Pending",    count: counts.pending,    color: "var(--text-3)" },
                { label: lang === "si" ? "සකසමින්" : "Processing", count: counts.processing, color: "var(--brand-mid)" },
                { label: lang === "si" ? "සුරකිනු" : "Done",      count: counts.done,       color: "#16a34a" },
                { label: lang === "si" ? "දෝෂ" : "Errors",       count: counts.error,      color: "#dc2626" },
                { label: lang === "si" ? "හමු" : "Skipped",      count: counts.skipped,    color: "#ea6c0a" },
              ].map(({ label, count, color }) => count > 0 && (
                <span key={label} className="text-[12px] font-bold" style={{ color }}>
                  {count} {label}
                </span>
              ))}
              <div className="ml-auto flex gap-2">
                {counts.done + counts.skipped > 0 && (
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
                    : <><span className="material-symbols-outlined text-[14px]">play_arrow</span>{lang === "si" ? "සියල්ල ආරම්භ කරන්න" : `Process all ${counts.pending}`}</>}
                </button>
              </div>
            </div>
          )}

          {/* Queue list */}
          {queue.length > 0 && (
            <div className="mt-4 space-y-2">
              {queue.map((item) => (
                <div key={item.id}
                  className="flex items-center gap-4 rounded-2xl px-4 py-3"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>

                  {/* Status icon */}
                  <span
                    className={`material-symbols-outlined text-[22px] ${item.status === "processing" ? "animate-spin" : ""}`}
                    style={{ color: statusColors[item.status] }}>
                    {statusIcons[item.status]}
                  </span>

                  {/* File info */}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-1)]">{item.file.name}</p>
                    <p className="text-[11px]" style={{ color: statusColors[item.status] }}>{item.message}</p>
                  </div>

                  {/* Doc type + total when done */}
                  {item.status === "done" && item.documentId && (
                    <div className="text-right">
                      <p className="text-[11px] font-bold uppercase text-[var(--text-3)]">{item.documentType}</p>
                      {item.total && item.total !== "NULL" && (
                        <p className="text-[12px] font-bold" style={{ color: "#16a34a" }}>LKR {item.total}</p>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2">
                    {item.status === "done" && item.documentId && (
                      <button onClick={() => router.push(`/analysis/${item.documentId}`)}
                        className="rounded-lg px-2 py-1 text-[10px] font-bold transition hover:opacity-80"
                        style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}>
                        {lang === "si" ? "විවෘත" : "Open"}
                      </button>
                    )}
                    {item.status !== "processing" && (
                      <button onClick={() => removeItem(item.id)}
                        className="text-[var(--text-3)] transition hover:text-red-500">
                        <span className="material-symbols-outlined text-[16px]">close</span>
                      </button>
                    )}
                  </div>
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
          {done && counts.pending === 0 && counts.processing === 0 && (
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
