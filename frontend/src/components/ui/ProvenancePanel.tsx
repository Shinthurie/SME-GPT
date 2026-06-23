"use client";

/**
 * Iteration 7 — Explainability UI.
 * Field-level provenance panel for the document analysis view.
 * Shows each extracted field with:
 *   - Confidence indicator (green/amber/red based on NULL / arithmetic status)
 *   - Source tag (OCR / LLM-corrected / arithmetic-validated)
 *   - Low-confidence warning for NULL or suspicious fields
 */

export type ArithmeticJson = {
  status?: string;
  computed_total?: number | null;
  raw_total?: number | null;
  mismatch?: boolean;
  items_sum?: number | null;
};

type FieldStatus = "ok" | "warn" | "missing";

function fieldStatus(value: unknown): FieldStatus {
  if (value === null || value === undefined) return "missing";
  const s = String(value).trim();
  if (s === "" || s.toUpperCase() === "NULL" || s.toUpperCase() === "NONE") return "missing";
  return "ok";
}

function FieldRow({
  label,
  value,
  source,
  warn,
}: {
  label: string;
  value: string;
  source: "ocr" | "llm" | "arithmetic" | "user";
  warn?: string;
}) {
  const status: FieldStatus = fieldStatus(value);

  const statusColor: Record<FieldStatus, string> = {
    ok: "bg-[#dcfce7] text-[#16a34a]",
    warn: "bg-amber-100 text-amber-700",
    missing: "bg-[#fee2e2] text-[#dc2626]",
  };

  const sourceLabel: Record<string, string> = {
    ocr: "OCR",
    llm: "LLM",
    arithmetic: "Arithmetic",
    user: "User",
  };

  const sourceBg: Record<string, string> = {
    ocr: "bg-[#eff6ff] text-[#2563ff]",
    llm: "bg-[#faf5ff] text-[#7c3aed]",
    arithmetic: "bg-[#fff7ed] text-[#ea580c]",
    user: "bg-[#f0fdf4] text-[#16a34a]",
  };

  return (
    <div className="flex flex-wrap items-start justify-between gap-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-[#475569]">{label}</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${sourceBg[source]}`}>
            {sourceLabel[source]}
          </span>
        </div>
        <p className={`mt-1 text-[14px] font-medium ${status === "missing" ? "text-[#94a3b8] italic" : "text-[#0f172a]"}`}>
          {status === "missing" ? "Not extracted" : value}
        </p>
        {warn && (
          <p className="mt-1 flex items-center gap-1 text-[11px] text-amber-600">
            <span className="material-symbols-outlined text-[13px]">warning</span>
            {warn}
          </p>
        )}
      </div>
      <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${statusColor[status]}`}>
        {status === "ok" ? "✓" : status === "warn" ? "!" : "✕"}
      </span>
    </div>
  );
}

export default function ProvenancePanel({
  doc,
  arithmeticJson,
}: {
  doc: Record<string, unknown>;
  arithmeticJson?: ArithmeticJson | null;
}) {
  const arithmeticStatus = String(doc.arithmetic_status || "").toLowerCase();
  const ocrVersion = String(doc.ocr_selected_version || "").trim();

  const totalWarn =
    arithmeticStatus === "mismatch"
      ? `Arithmetic mismatch: computed ${arithmeticJson?.computed_total?.toFixed(2) ?? "?"}, extracted ${arithmeticJson?.raw_total?.toFixed(2) ?? "?"}`
      : undefined;

  return (
    <div className="rounded-[18px] border border-[#e2e8f0] bg-[#f8fafc] px-5 py-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
          Field Provenance
        </p>
        <div className="flex items-center gap-2">
          {ocrVersion && (
            <span className="rounded-xl bg-[#eff6ff] px-3 py-1 text-[10px] font-semibold text-[#2563ff]">
              OCR: {ocrVersion}
            </span>
          )}
          <span
            className={`rounded-xl px-3 py-1 text-[10px] font-bold ${
              arithmeticStatus === "ok"
                ? "bg-[#dcfce7] text-[#16a34a]"
                : arithmeticStatus === "mismatch"
                ? "bg-amber-100 text-amber-700"
                : "bg-[#f1f5f9] text-[#64748b]"
            }`}
          >
            Arithmetic: {arithmeticStatus || "not checked"}
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <FieldRow label="Document Type"    value={String(doc.document_type    || "")} source="llm" />
        <FieldRow label="Company / Buyer"  value={String(doc.company_name     || "")} source="llm" />
        <FieldRow label="Supplier"         value={String(doc.supplier_name    || "")} source="llm" />
        <FieldRow label="Date"             value={String(doc.date             || "")} source="ocr" />
        <FieldRow label="Order ID"         value={String(doc.order_id         || "")} source="ocr" />
        <FieldRow
          label="Final Total"
          value={String(doc.final_total_amount || "")}
          source="arithmetic"
          warn={totalWarn}
        />
        <FieldRow label="Payable Amount"   value={String(doc.payable_amount   || "")} source="arithmetic" />
        <FieldRow label="Currency"         value={String(doc.currency         || "")} source="llm" />
        <FieldRow label="Flow Type"        value={String(doc.flow_type        || "")} source="llm" />
        <FieldRow label="Language"         value={String(doc.language         || "")} source="llm" />
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-2 border-t border-[#e2e8f0] pt-3">
        <span className="text-[10px] font-semibold text-[#94a3b8]">Source key:</span>
        {[
          { key: "ocr", label: "Directly from OCR" },
          { key: "llm", label: "LLM-extracted" },
          { key: "arithmetic", label: "Arithmetic-validated" },
        ].map(({ key, label }) => (
          <span
            key={key}
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
              key === "ocr"
                ? "bg-[#eff6ff] text-[#2563ff]"
                : key === "llm"
                ? "bg-[#faf5ff] text-[#7c3aed]"
                : "bg-[#fff7ed] text-[#ea580c]"
            }`}
          >
            {key.toUpperCase()} — {label}
          </span>
        ))}
      </div>
    </div>
  );
}
