"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import ProvenancePanel, { type ArithmeticJson } from "@/components/ui/ProvenancePanel";
import BboxOverlayViewer from "@/components/ui/BboxOverlayViewer";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

type Item = {
  description: string;
  quantity: string | number;
  unit_price: string | number;
  line_total?: string | number;
};

type DocumentDetail = {
  document_id: string;
  document_type: string;
  company_name: string;
  supplier_name: string;
  date: string;
  raw_total_amount: string;
  final_total_amount: string;
  payable_amount: string;
  cash_return?: string;
  currency: string;
  status: string;
  language: string;
  order_id: string;
  flow_type: string;
  received_status: string;
  paid_status: string;
  items: Item[];
  image_url?: string | null;
  // Provenance fields (Iteration 7)
  arithmetic_status?: string;
  arithmetic_json?: ArithmeticJson | null;
  ocr_selected_version?: string;
  corrected_text?: string;
  // Spatial blobs (Iteration 9 + 10)
  spatial_chunks_json?: string | null;
  safe_boxes_json?: string | null;
  // Field→chunk map (Iteration 18 GAP-18C)
  field_chunk_map_json?: string | null;
  // Tax fields
  tax_amount?: string | number | null;
  tax_rate?: string | number | null;
  // Cash flow tracking
  cash_inflowed?: string | number | null;
  cash_outflowed?: string | number | null;
  category?: string | null;
};

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function InfoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
        {title}
      </p>
      <div className="mt-3 text-[14px] leading-7 text-[#334155]">{children}</div>
    </div>
  );
}

export default function AnalysisDetailPage() {
  const router = useRouter();
  const pathname = usePathname();

  const [lang, setLang] = useState<AppLanguage>("en");
  const [showProvenance, setShowProvenance] = useState(false);
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null);
  const t = ui[lang];
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [editedDocument, setEditedDocument] = useState<DocumentDetail | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [flowChangeMessage, setFlowChangeMessage] = useState("");

  const documentId = useMemo(() => {
    if (!pathname) return "";
    const parts = pathname.split("/").filter(Boolean);
    return parts.length >= 2 ? decodeURIComponent(parts[parts.length - 1]) : "";
  }, [pathname]);

  useEffect(() => {
    setLang(getStoredLanguage());
  }, []);

  useEffect(() => {
    if (!documentId) {
      setLoading(false);
      setError("Document ID is missing.");
      return;
    }

    const fetchDocument = async () => {
      const token = getAuthToken();

      if (!token) {
        setError("Login token missing. Please log in again.");
        setLoading(false);
        router.push("/login");
        return;
      }

      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${BACKEND_URL}/documents/${documentId}`, {
          method: "GET",
          cache: "no-store",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (res.status === 401) {
          localStorage.removeItem("token");
          sessionStorage.removeItem("token");
          router.push("/login");
          return;
        }

        const data = await res.json();

        if (!res.ok || !data.success) {
          throw new Error(data.message || "Failed to load document.");
        }

        setDocument(data.document);
        setEditedDocument(data.document);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load document.");
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [documentId, router]);

  const formatParty = () => {
    const target = editedDocument || document;
    if (!target) return "NULL";
    if (target.company_name && target.company_name !== "NULL") return target.company_name;
    if (target.supplier_name && target.supplier_name !== "NULL") return target.supplier_name;
    return "NULL";
  };

  const updateField = <K extends keyof DocumentDetail>(
    key: K,
    value: DocumentDetail[K]
  ) => {
    setEditedDocument((prev) => {
      if (!prev) return prev;
      return { ...prev, [key]: value };
    });
  };

  const updateItemField = <K extends keyof Item>(
    index: number,
    key: K,
    value: Item[K]
  ) => {
    setEditedDocument((prev) => {
      if (!prev) return prev;
      const updatedItems = [...(prev.items || [])];
      updatedItems[index] = {
        ...updatedItems[index],
        [key]: value,
      };
      return {
        ...prev,
        items: updatedItems,
      };
    });
  };

  const handleSave = async () => {
    if (!editedDocument) return;

    try {
      setSaving(true);
      setError("");
      setSuccessMessage("");

      const token = getAuthToken();
      const res = await fetch(`${BACKEND_URL}/documents/${documentId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          company_name: editedDocument.company_name,
          supplier_name: editedDocument.supplier_name,
          date: editedDocument.date,
          document_type: editedDocument.document_type,
          order_id: editedDocument.order_id,
          flow_type: editedDocument.flow_type,
          currency: editedDocument.currency,
          raw_total_amount: editedDocument.raw_total_amount,
          final_total_amount: editedDocument.final_total_amount,
          payable_amount: editedDocument.payable_amount,
          cash_return: editedDocument.cash_return,
          cash_inflowed: editedDocument.cash_inflowed,
          cash_outflowed: editedDocument.cash_outflowed,
          received_status: editedDocument.received_status,
          paid_status: editedDocument.paid_status,
          language: editedDocument.language,
          items: editedDocument.items,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to update document.");
      }

      setDocument(data.document);
      setEditedDocument(data.document);
      setEditMode(false);

      if (data.flow_change_message) {
        setFlowChangeMessage(data.flow_change_message);
      } else {
        setFlowChangeMessage("");
      }

      setSuccessMessage("Document updated successfully.");


    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update document.");
    } finally {
      setSaving(false);
    }
  };

  const target = editedDocument || document;
    const handleDelete = async () => {
    if (!documentId) return;

    const confirmed = window.confirm(
      "Are you sure you want to delete this document?"
    );

    if (!confirmed) return;

    try {
      setDeleting(true);
      setError("");
      setSuccessMessage("");

      const token = getAuthToken();

      const res = await fetch(`${BACKEND_URL}/documents/${documentId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Failed to delete document.");
      }

      router.push("/repository");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document.");
    } finally {
      setDeleting(false);
    }
  };

  
  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={() => router.back()}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#2563ff] transition hover:bg-[#eef4ff]"
            >
              <span className="material-symbols-outlined">arrow_back</span>
            </button>

            <div className="flex items-center gap-2">
  <LanguageSwitcher />

  {!loading && target ? (
    <>
      <button
        onClick={() => {
          if (editMode) {
            setEditedDocument(document);
            setEditMode(false);
            setFlowChangeMessage("");
          } else {
            setEditMode(true);
          }
        }}
        className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-semibold text-[#2563ff]"
      >
        {editMode ? "Cancel" : "Edit"}
      </button>

      <button
        onClick={handleSave}
        disabled={saving || !editMode}
        className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-[13px] font-bold text-white disabled:opacity-40"
        style={{ background: "#2252b5" }}
      >
        <span className="material-symbols-outlined text-[14px]">verified</span>
        {saving ? "Saving…" : "Verify Data"}
      </button>

      <button
        onClick={handleDelete}
        disabled={deleting}
        className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-[13px] font-semibold text-red-600 disabled:opacity-60"
      >
        {deleting ? "Deleting..." : "Delete"}
      </button>
    </>
  ) : null}
</div>
          </div>

          <div className="mb-5">
            <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
              {loading ? "Loading..." : target?.document_id || "Document"}
            </h1>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Financial Document Analysis
            </p>
          </div>

          {successMessage && (
            <div className="mb-4 rounded-[18px] border border-green-200 bg-green-50 p-4 text-[14px] text-green-700">
              {successMessage}
            </div>
          )}
          {flowChangeMessage && (
  <div className="mb-4 rounded-[18px] border border-amber-200 bg-amber-50 p-4 text-[14px] text-amber-800">
    {flowChangeMessage}
  </div>
)}
          {loading ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              Loading document...
            </div>
          ) : error ? (
            <div className="rounded-[18px] border border-red-200 bg-red-50 p-6 text-center text-[14px] text-red-700">
              {error}
            </div>
          ) : !target ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              Document not found.
            </div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
              <div className="rounded-[20px] bg-[#eef2f7] p-3 shadow-sm">
                {/* Language region tag */}
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className="rounded-lg px-3 py-1 text-[10px] font-bold uppercase tracking-wider"
                    style={{ background: "rgba(34,82,181,0.1)", color: "#2252b5" }}
                  >
                    {target.language && target.language !== "NULL"
                      ? `${target.language.toUpperCase()} REGION`
                      : "ENGLISH REGION"}
                  </span>
                </div>
                <div className="rounded-[16px] bg-white p-3">
                  {target.image_url ? (
                    <BboxOverlayViewer
                      imageUrl={`${BACKEND_URL}${target.image_url}`}
                      documentId={target.document_id}
                      spatialChunksJson={target.spatial_chunks_json}
                      activeChunkId={activeChunkId}
                      onChunkSelect={setActiveChunkId}
                    />
                  ) : (
                    <div className="flex min-h-[420px] items-center justify-center rounded-[16px] bg-[#f3f4f6] sm:min-h-[520px]">
                      <div className="text-[13px] text-[#94a3b8]">
                        No saved preview image for this document
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <div className="rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
                        {lang === "si" ? "උකහා ගත් දත්ත" : "Extracted Data"}
                      </p>
                      <h2 className="text-[18px] font-extrabold text-[#0f172a] sm:text-[20px]">
                        Document Detail
                      </h2>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-xl bg-[#eef4ff] px-3 py-2 text-[12px] font-semibold text-[#2563ff]">
                        {target.document_type?.toUpperCase() || "UNKNOWN"}
                      </span>
                      <span className="rounded-xl bg-[#f1f5f9] px-3 py-2 text-[12px] text-[#334155]">
                        {target.currency || "NULL"}
                      </span>
                      <span className="rounded-xl bg-[#dcfce7] px-3 py-2 text-[12px] font-semibold text-[#16a34a]">
                        {target.status || "ready"}
                      </span>
                    </div>
                  </div>

                  {/* AI/OCR Confidence badge */}
                  <div className="mt-3 flex items-center gap-2">
                    <span
                      className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-bold"
                      style={{ background: "rgba(34,82,181,0.08)", color: "#2252b5" }}
                    >
                      <span className="material-symbols-outlined text-[13px]">smart_toy</span>
                      AI / OCR
                    </span>
                    <span
                      className="rounded-lg px-3 py-1.5 text-[11px] font-bold"
                      style={
                        target.arithmetic_status === "matched"
                          ? { background: "rgba(22,163,74,0.08)", color: "#16a34a" }
                          : target.arithmetic_status === "mismatch"
                          ? { background: "rgba(220,38,38,0.08)", color: "#dc2626" }
                          : { background: "rgba(100,116,139,0.08)", color: "#64748b" }
                      }
                    >
                      {target.arithmetic_status === "matched" ? "99% CONFIDENCE"
                        : target.arithmetic_status === "mismatch" ? "VERIFY TOTALS"
                        : "OCR PROCESSED"}
                    </span>
                  </div>
                </div>

                <div className="mt-4 space-y-4">
                  <InfoCard title={t.metadataTitle}>
                    <span className="font-semibold text-[#0f172a]">{t.documentIdLabel}:</span> {target.document_id}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.orderIdLabel}:</span>{" "}
                    {editMode ? (
                      <input
                        value={target.order_id || ""}
                        onChange={(e) => updateField("order_id", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      />
                    ) : target.order_id || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.dateLabel}:</span>{" "}
                    {editMode ? (
                      <input
                        value={target.date || ""}
                        onChange={(e) => updateField("date", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      />
                    ) : target.date || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.partyLabel}:</span> {formatParty()}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.flowTypeLabel}:</span>{" "}
                    {editMode ? (
                      <select
                        value={target.flow_type || "unknown"}
                        onChange={(e) => updateField("flow_type", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      >
                        <option value="unknown">unknown</option>
                        <option value="payable">payable</option>
                        <option value="receivable">receivable</option>
                        <option value="cash_inflow">cash inflow</option>
                        <option value="cash_outflow">cash outflow</option>
                      </select>
                    ) : target.flow_type || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.categoryLabel}:</span>{" "}
                    {(() => {
                      const ft = (target.flow_type || "").toLowerCase();
                      const derived = (target.category && target.category !== "NULL")
                        ? target.category
                        : ["receivable","cash_inflow"].includes(ft) ? t.categoryRevenue
                        : ["payable","cash_outflow"].includes(ft) ? t.categoryExpenses
                        : t.categoryUnknown;
                      return (
                        <span className={`ml-1 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold ${
                          derived === "Revenue"  ? "bg-green-50 text-green-700" :
                          derived === "Expenses" ? "bg-red-50 text-red-700"    :
                                                   "bg-slate-50 text-slate-500"
                        }`}>{derived}</span>
                      );
                    })()}
                  </InfoCard>

                  <InfoCard title={t.partiesTitle}>
                    <span className="font-semibold text-[#0f172a]">{t.companyLabel2}:</span>{" "}
                    {editMode ? (
                      <input
                        value={target.company_name || ""}
                        onChange={(e) => updateField("company_name", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      />
                    ) : target.company_name || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">
                      {["receivable","cash_inflow"].includes(target.flow_type || "") ? `${t.customerLabel}:` : `${t.supplierLabel2}:`}
                    </span>{" "}
                    {editMode ? (
                      <input
                        value={target.supplier_name || ""}
                        onChange={(e) => updateField("supplier_name", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      />
                    ) : target.supplier_name || "NULL"}
                  </InfoCard>

                  <InfoCard title={t.financialSummaryTitle}>
                    {(() => {
                      const ft  = (target.flow_type || "").toLowerCase();
                      const cur = target.currency && target.currency !== "NULL" ? target.currency : "LKR";
                      const finalTotal    = parseFloat(String(target.final_total_amount ?? 0)) || 0;
                      const cashInflowed  = parseFloat(String(target.cash_inflowed  ?? 0)) || 0;
                      const cashOutflowed = parseFloat(String(target.cash_outflowed ?? 0)) || 0;
                      const receivableAmt = Math.max(0, finalTotal - cashInflowed);
                      const payableAmt    = Math.max(0, finalTotal - cashOutflowed);

                      return (
                        <>
                          {/* Raw total always shown */}
                          <span className="font-semibold text-[#0f172a]">{t.rawTotalLabel}:</span>{" "}
                          {editMode ? (
                            <input value={String(target.raw_total_amount || "")} onChange={(e) => updateField("raw_total_amount", e.target.value)} className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]" />
                          ) : target.raw_total_amount || "NULL"}
                          <br />

                          {/* Final total always shown */}
                          <span className="font-semibold text-[#0f172a]">{t.finalTotalLabel}:</span>{" "}
                          {editMode ? (
                            <input value={String(target.final_total_amount || "")} onChange={(e) => updateField("final_total_amount", e.target.value)} className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]" />
                          ) : `${cur} ${finalTotal.toFixed(2)}`}
                          <br />

                          {/* RECEIVABLE — track partial payments */}
                          {ft === "receivable" && (
                            <>
                              <span className="font-semibold text-[#0f172a]">{t.cashInflowedLabel}:</span>{" "}
                              {editMode ? (
                                <input type="number" min="0" value={String(target.cash_inflowed ?? "")} onChange={(e) => updateField("cash_inflowed", e.target.value)} className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px] w-32" />
                              ) : `${cur} ${cashInflowed.toFixed(2)}`}
                              <br />
                              <span className="font-semibold text-[#0f172a]">{t.receivableAmountLabel}:</span>{" "}
                              <span className={receivableAmt === 0 ? "ml-1 font-bold text-green-600" : "ml-1 font-bold text-[#2252b5]"}>
                                {cur} {receivableAmt.toFixed(2)}{receivableAmt === 0 ? " {t.fullyReceived}" : ""}
                              </span>
                              <br />
                            </>
                          )}

                          {/* CASH INFLOW — amount is the final total, no tracking needed */}
                          {ft === "cash_inflow" && (
                            <>
                              <span className="font-semibold text-[#0f172a]">{t.cashInflowedLabel}:</span>{" "}
                              <span className="ml-1 font-bold text-green-600">{cur} {finalTotal.toFixed(2)} ✓ Received</span>
                              <br />
                            </>
                          )}

                          {/* PAYABLE — track partial payments */}
                          {ft === "payable" && (
                            <>
                              <span className="font-semibold text-[#0f172a]">{t.cashOutflowedLabel}:</span>{" "}
                              {editMode ? (
                                <input type="number" min="0" value={String(target.cash_outflowed ?? "")} onChange={(e) => updateField("cash_outflowed", e.target.value)} className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px] w-32" />
                              ) : `${cur} ${cashOutflowed.toFixed(2)}`}
                              <br />
                              <span className="font-semibold text-[#0f172a]">{t.payableAmountLabel}:</span>{" "}
                              <span className={payableAmt === 0 ? "ml-1 font-bold text-green-600" : "ml-1 font-bold text-[#dc2626]"}>
                                {cur} {payableAmt.toFixed(2)}{payableAmt === 0 ? " {t.fullyPaid}" : ""}
                              </span>
                              <br />
                            </>
                          )}

                          {/* CASH OUTFLOW — amount is the final total, no tracking needed */}
                          {ft === "cash_outflow" && (
                            <>
                              <span className="font-semibold text-[#0f172a]">{t.cashOutflowedLabel}:</span>{" "}
                              <span className="ml-1 font-bold text-green-600">{cur} {finalTotal.toFixed(2)} ✓ Paid</span>
                              <br />
                            </>
                          )}

                          <span className="font-semibold text-[#0f172a]">{t.currencyLabel}:</span>{" "}
                          {editMode ? (
                            <input value={target.currency || ""} onChange={(e) => updateField("currency", e.target.value)} className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]" />
                          ) : target.currency || "NULL"}
                        </>
                      );
                    })()}
                  </InfoCard>

                  <InfoCard title={t.statusTitle}>
                    <span className="font-semibold text-[#0f172a]">{t.receivedStatusLabel}:</span>{" "}
{editMode ? (
  <select
    value={target.received_status || "NULL"}
    onChange={(e) => updateField("received_status", e.target.value)}
    className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
  >
    <option value="NULL">NULL</option>
    <option value="received">received</option>
    <option value="not_received">not_received</option>
    <option value="partial">partial</option>
  </select>
) : target.received_status || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.paidStatusLabel}:</span>{" "}
{editMode ? (
  <select
    value={target.paid_status || "NULL"}
    onChange={(e) => updateField("paid_status", e.target.value)}
    className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
  >
    <option value="NULL">NULL</option>
    <option value="paid">paid</option>
    <option value="not_paid">not_paid</option>
    <option value="partial">partial</option>
  </select>
) : target.paid_status || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">{t.languageLabel}:</span>{" "}
                    {editMode ? (
                      <select
                        value={target.language || "en"}
                        onChange={(e) => updateField("language", e.target.value)}
                        className="ml-2 rounded border border-slate-200 px-2 py-1 text-[13px]"
                      >
                        <option value="en">en</option>
                        <option value="si">si</option>
                      </select>
                    ) : target.language || "NULL"}
                  </InfoCard>

                  {/* TAX DETAILS — shows only when tax was extracted from the document */}
                  <InfoCard title={t.taxDetailsTitle}>
                    {(() => {
                      const rawTax = target.tax_amount;
                      const rawRate = target.tax_rate;
                      const taxAmt = rawTax != null && rawTax !== "NULL" && rawTax !== "" ? parseFloat(String(rawTax)) : null;
                      const taxRate = rawRate != null && rawRate !== "NULL" && rawRate !== "" ? parseFloat(String(rawRate)) : null;
                      const cur = target.currency && target.currency !== "NULL" ? target.currency : "LKR";

                      if (taxAmt !== null && !isNaN(taxAmt) && taxAmt > 0) {
                        const label = taxRate !== null && !isNaN(taxRate)
                          ? `Tax (${taxRate}%)`
                          : "Tax";
                        return (
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-[#0f172a]">{label}</span>
                            <span className="font-bold text-[#2252b5]">{cur} {taxAmt.toFixed(2)}</span>
                          </div>
                        );
                      }
                      return <span className="text-[#94a3b8]">{t.noTaxOnDocument}</span>;
                    })()}
                  </InfoCard>

                  <div className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
                    <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
                      {t.itemsTitle}
                    </p>

                    <div className="mt-3 space-y-3">
                      {target.items && target.items.length > 0 ? (
                        target.items.map((item, index) => (
                          <div
                            key={index}
                            className="grid gap-2 rounded-[12px] border border-slate-200 p-3 sm:grid-cols-3"
                          >
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">{t.descriptionLabel}:</span>{" "}
                              {editMode ? (
                                <input
                                  value={String(item.description || "")}
                                  onChange={(e) => updateItemField(index, "description", e.target.value)}
                                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-[13px]"
                                />
                              ) : item.description || "NULL"}
                            </div>
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">{t.quantityLabel}:</span>{" "}
                              {editMode ? (
                                <input
                                  value={String(item.quantity ?? "")}
                                  onChange={(e) => updateItemField(index, "quantity", e.target.value)}
                                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-[13px]"
                                />
                              ) : item.quantity ?? "NULL"}
                            </div>
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">{t.unitPriceLabel}:</span>{" "}
                              {editMode ? (
                                <input
                                  value={String(item.unit_price ?? "")}
                                  onChange={(e) => updateItemField(index, "unit_price", e.target.value)}
                                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-[13px]"
                                />
                              ) : item.unit_price ?? "NULL"}
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-[14px] text-[#64748b]">No items available.</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Provenance Panel — Iteration 7 */}
                <div className="mt-4 rounded-[18px] border border-slate-200 bg-white shadow-sm">
                  <button
                    onClick={() => setShowProvenance((prev) => !prev)}
                    className="flex w-full items-center justify-between px-5 py-4 text-left"
                  >
                    <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                      {t.fieldProvenance ?? "Field Provenance"}
                    </span>
                    <span className="material-symbols-outlined text-[#64748b]">
                      {showProvenance ? "expand_less" : "expand_more"}
                    </span>
                  </button>
                  {showProvenance && (
                    <div className="border-t border-slate-100 px-4 py-4">
                      <ProvenancePanel
                        doc={target as Record<string, unknown>}
                        arithmeticJson={target.arithmetic_json}
                        activeChunkId={activeChunkId}
                        fieldChunkMap={
                          target.field_chunk_map_json
                            ? (() => { try { return JSON.parse(target.field_chunk_map_json!); } catch { return null; } })()
                            : null
                        }
                        onChunkSelect={setActiveChunkId}
                      />
                    </div>
                  )}
                </div>

                {editMode ? (
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="mt-5 w-full rounded-[18px] bg-[#2563ff] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)] disabled:opacity-60"
                  >
                    {saving ? "Saving..." : "Save Changes"}
                  </button>
                ) : (
                  <button
                    onClick={() => router.push("/repository")}
                    className="mt-5 w-full rounded-[18px] bg-[#2563ff] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)]"
                  >
                    {t.backToDashboard ?? "Back to Repository"}
                  </button>
                )}
              </div>
            </div>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}