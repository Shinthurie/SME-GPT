"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type BulkEntry = {
  id: string;
  fileName: string;
  status: "pending" | "processing" | "ready" | "saving" | "done" | "error" | "skipped" | "cancelled";
  sessionId?: string;
};

const STATUS_COLOR: Record<string, string> = {
  pending:    "#94a3b8",
  processing: "#2563eb",
  ready:      "#0891b2",
  saving:     "#2563eb",
  done:       "#16a34a",
  error:      "#dc2626",
  skipped:    "#ea6c0a",
  cancelled:  "#94a3b8",
};
const STATUS_ICON: Record<string, string> = {
  pending:    "hourglass_empty",
  processing: "progress_activity",
  ready:      "fact_check",
  saving:     "progress_activity",
  done:       "check_circle",
  error:      "error",
  skipped:    "warning",
  cancelled:  "block",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "Pending", processing: "Processing…", ready: "Ready for review",
  saving: "Saving…", done: "Saved", error: "Error", skipped: "Duplicate", cancelled: "Cancelled",
};

function readQueue(): BulkEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem("sme_bulk_queue") || "[]");
  } catch {
    return [];
  }
}

export default function BulkProcessingWidget() {
  const router = useRouter();
  const [queue, setQueue] = useState<BulkEntry[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const refresh = () => setQueue(readQueue());

  useEffect(() => {
    refresh();
    window.addEventListener("sme-bulk-updated", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("sme-bulk-updated", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  // Reset dismiss when new items arrive
  useEffect(() => {
    const active = queue.filter((e) => ["processing", "ready"].includes(e.status));
    if (active.length > 0) setDismissed(false);
  }, [queue]);

  const active = queue.filter((e) => ["processing", "ready"].includes(e.status));
  const total = queue.filter((e) => e.status !== "done" && e.status !== "cancelled" && e.status !== "skipped");

  if (dismissed || (active.length === 0 && queue.length === 0)) return null;

  const processingCount = queue.filter((e) => e.status === "processing").length;
  const readyCount = queue.filter((e) => e.status === "ready").length;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 88,
        right: 16,
        zIndex: 9999,
        width: expanded ? 320 : "auto",
        maxHeight: expanded ? 420 : "auto",
        borderRadius: 18,
        boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
        background: "var(--surface, #ffffff)",
        border: "1px solid var(--border, #e2e8f0)",
        overflow: "hidden",
        transition: "width 0.2s ease, max-height 0.2s ease",
      }}
    >
      {/* Header chip */}
      <div
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: expanded ? "10px 14px" : "8px 12px",
          cursor: "pointer",
          background: processingCount > 0 ? "rgba(37,99,235,0.06)" : readyCount > 0 ? "rgba(8,145,178,0.06)" : "rgba(22,163,74,0.06)",
          borderBottom: expanded ? "1px solid var(--border, #e2e8f0)" : "none",
        }}
      >
        <span
          className={`material-symbols-outlined ${processingCount > 0 ? "animate-spin" : ""}`}
          style={{
            fontSize: 18,
            color: processingCount > 0 ? "#2563eb" : readyCount > 0 ? "#0891b2" : "#16a34a",
          }}
        >
          {processingCount > 0 ? "progress_activity" : readyCount > 0 ? "fact_check" : "check_circle"}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          {!expanded && (
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-1, #0f172a)" }}>
              {processingCount > 0
                ? `Processing ${processingCount} document${processingCount !== 1 ? "s" : ""}…`
                : readyCount > 0
                ? `${readyCount} ready for review`
                : `${queue.filter((e) => e.status === "done").length} saved`}
            </span>
          )}
          {expanded && (
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-1, #0f172a)" }}>
              Document Processing
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {readyCount > 0 && (
            <span style={{
              background: "#0891b2", color: "#fff", borderRadius: 999,
              padding: "1px 7px", fontSize: 11, fontWeight: 700,
            }}>
              {readyCount} ready
            </span>
          )}
          {processingCount > 0 && (
            <span style={{
              background: "#2563eb", color: "#fff", borderRadius: 999,
              padding: "1px 7px", fontSize: 11, fontWeight: 700,
            }}>
              {processingCount}
            </span>
          )}
          <span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--text-3, #94a3b8)" }}>
            {expanded ? "expand_more" : "expand_less"}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); setDismissed(true); }}
            style={{
              background: "none", border: "none", cursor: "pointer", padding: 0,
              color: "var(--text-3, #94a3b8)", display: "flex", alignItems: "center",
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
          </button>
        </div>
      </div>

      {/* Expanded list */}
      {expanded && (
        <div style={{ overflowY: "auto", maxHeight: 340, padding: "8px 0" }}>
          {queue.length === 0 && (
            <p style={{ padding: "12px 14px", fontSize: 13, color: "var(--text-3, #94a3b8)" }}>
              No documents in queue.
            </p>
          )}
          {queue.map((entry) => (
            <div
              key={entry.id}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 14px",
                borderBottom: "1px solid var(--border, #f1f5f9)",
              }}
            >
              <span
                className={`material-symbols-outlined ${entry.status === "processing" || entry.status === "saving" ? "animate-spin" : ""}`}
                style={{ fontSize: 18, color: STATUS_COLOR[entry.status] ?? "#94a3b8", flexShrink: 0 }}
              >
                {STATUS_ICON[entry.status] ?? "description"}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-1, #0f172a)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {entry.fileName}
                </p>
                <p style={{ fontSize: 11, color: STATUS_COLOR[entry.status] ?? "#94a3b8" }}>
                  {STATUS_LABEL[entry.status] ?? entry.status}
                </p>
              </div>
              {entry.status === "ready" && entry.sessionId && (
                <button
                  onClick={() => { setExpanded(false); router.push(`/bulk-review/${entry.sessionId}`); }}
                  style={{
                    background: "rgba(8,145,178,0.1)", color: "#0891b2",
                    border: "none", borderRadius: 8, padding: "3px 10px",
                    fontSize: 11, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
                  }}
                >
                  Review
                </button>
              )}
            </div>
          ))}

          {/* Go to bulk upload button */}
          <div style={{ padding: "8px 14px" }}>
            <button
              onClick={() => { setExpanded(false); router.push("/bulk-upload"); }}
              style={{
                width: "100%", background: "var(--brand-tint, #eef4ff)",
                color: "var(--brand-mid, #2563eb)", border: "none",
                borderRadius: 10, padding: "7px 0", fontSize: 12,
                fontWeight: 700, cursor: "pointer",
              }}
            >
              Open Bulk Upload
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
