"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

type PreviewItem = {
  description: string;
  quantity: string | number;
  unit_price: string | number;
};

type PreviewData = {
  document_type: string;
  order_id: string;
  flow_type: string;
  company_name: string;
  supplier_name: string;
  date: string;
  currency: string;
  raw_total_amount: string | number;
  final_total_amount: string | number;
  payable_amount: string | number;
  cash_return: string | number;
  received_status: string;
  paid_status: string;
  items: PreviewItem[];
};

const BACKEND_URL ="http://127.0.0.1:8000";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [lang, setLang] = useState<AppLanguage>("en");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const [duplicateMessage, setDuplicateMessage] = useState("");
  const [existingDocumentId, setExistingDocumentId] = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
  }, []);

  const t = ui[lang];

  const handleOpenFilePicker = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    setPreview(null);
    setError("");
    setSuccessMessage("");
    setSessionId("");
    setShowDuplicateWarning(false);
    setDuplicateMessage("");
    setExistingDocumentId("");
  };

  const resetAfterSuccessfulSave = () => {
    setPreview(null);
    setSelectedFile(null);
    setSessionId("");
    setShowDuplicateWarning(false);
    setDuplicateMessage("");
    setExistingDocumentId("");
    setError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setPreview(null);
    setError("");
    setSuccessMessage("");
    setSessionId("");
    setShowDuplicateWarning(false);
    setDuplicateMessage("");
    setExistingDocumentId("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const formatFileSize = (size: number) => {
    if (size < 1024 * 1024) {
      return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = () => {
    if (!selectedFile) return "upload_file";
    if (selectedFile.type.includes("pdf")) return "picture_as_pdf";
    return "image";
  };

  const getFileIconBg = () => {
    if (!selectedFile) return "bg-[#eaf0ff] text-[#2563ff]";
    if (selectedFile.type.includes("pdf")) return "bg-[#fff1f1] text-[#ef4444]";
    return "bg-[#ecfeff] text-[#0891b2]";
  };

  const handleStartProcessing = async () => {
    if (!selectedFile) return;

    const token = getAuthToken();
    if (!token) {
      setError("Login token missing. Please log in again.");
      router.push("/login");
      return;
    }

    setIsProcessing(true);
    setError("");
    setSuccessMessage("");
    setPreview(null);
    setSessionId("");
    setShowDuplicateWarning(false);
    setDuplicateMessage("");
    setExistingDocumentId("");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch(`${BACKEND_URL}/process-document`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        router.push("/login");
        return;
      }

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Processing failed");
      }

      setPreview(data.preview);
      setSessionId(data.session_id);
    } catch (err: any) {
      setError(err.message || "Something went wrong during processing.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFieldChange = (field: keyof PreviewData, value: string) => {
    if (!preview) return;
    setPreview({
      ...preview,
      [field]: value,
    });
  };

  const handleItemChange = (
    index: number,
    field: keyof PreviewItem,
    value: string
  ) => {
    if (!preview) return;
    const updatedItems = [...preview.items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: value,
    };

    setPreview({
      ...preview,
      items: updatedItems,
    });
  };

  const handleConfirmSave = async (forceSave = false) => {
    if (!preview || !sessionId) return;

    const token = getAuthToken();
    if (!token) {
      setError("Login token missing. Please log in again.");
      router.push("/login");
      return;
    }

    setIsSaving(true);
    setError("");
    setSuccessMessage("");

    try {
      const res = await fetch(`${BACKEND_URL}/confirm-save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          edited_preview: preview,
          force_save: forceSave,
        }),
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        router.push("/login");
        return;
      }

      const data = await res.json();

      if (data.duplicate_found && !data.success) {
        setShowDuplicateWarning(true);
        setDuplicateMessage(data.message || "Already we have this document.");
        setExistingDocumentId(data.existing_document_id || "NULL");
        return;
      }

      if (!res.ok || !data.success) {
        throw new Error(data.message || "Save failed.");
      }

      setShowDuplicateWarning(false);
      setDuplicateMessage("");
      setExistingDocumentId("");
      setSuccessMessage(`Successfully saved. Document ID: ${data.document_id}`);
      resetAfterSuccessfulSave();
    } catch (err: any) {
      setError(err.message || "Something went wrong while saving.");
    } finally {
      setIsSaving(false);
    }
  };

  const renderProcessButtonText = () => {
    if (isProcessing) return "Processing...";
    if (preview) return "Processing Done";
    return t.startProcessing;
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← {t.backToDashboard}
            </button>
            <LanguageSwitcher />
          </div>

          <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
            {t.uploadTitle}
          </h1>
          <p className="mt-2 max-w-3xl text-[13px] leading-7 text-[#64748b] sm:text-[14px]">
            {t.uploadSubtitle}
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            className="hidden"
            onChange={handleFileChange}
          />

          <div className="mt-8 rounded-[22px] border-2 border-dashed border-[#a9c1ff] bg-white p-8 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#eaf0ff]">
              <span className="material-symbols-outlined text-[30px] text-[#2563ff]">
                {selectedFile ? getFileIcon() : "upload_file"}
              </span>
            </div>

            <h2 className="mt-5 text-[18px] font-bold text-[#0f172a]">
              {selectedFile ? selectedFile.name : t.dragDrop}
            </h2>

            <p className="mt-2 text-[13px] text-[#64748b]">
              {selectedFile
                ? `${formatFileSize(selectedFile.size)} • Ready for OCR extraction`
                : t.maxFileSize}
            </p>

            <button
              onClick={handleOpenFilePicker}
              className="mt-5 rounded-2xl bg-[#dfe7fb] px-6 py-3 text-[14px] font-semibold text-[#2563ff]"
            >
              {selectedFile ? "Choose Another File" : t.selectDevice}
            </button>
          </div>

          {selectedFile && (
            <div className="mt-5 rounded-[18px] border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-4">
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-xl ${getFileIconBg()}`}
                >
                  <span className="material-symbols-outlined text-[24px]">
                    {getFileIcon()}
                  </span>
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-[16px] font-semibold text-[#0f172a]">
                    {selectedFile.name}
                  </p>
                  <p className="text-[12px] text-[#94a3b8]">
                    {formatFileSize(selectedFile.size)} • Ready for OCR extraction
                  </p>
                </div>

                <button onClick={handleRemoveFile} className="text-[#94a3b8]">
                  <span className="material-symbols-outlined text-[24px]">
                    close
                  </span>
                </button>
              </div>
            </div>
          )}

          <div className="mt-8 flex items-center justify-between">
            <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-[#94a3b8]">
              {t.processingPipeline}
            </p>
            <p className="text-[13px] text-[#2563ff]">{t.explainableAI}</p>
          </div>

          <div className="mt-5 space-y-6">
            {[
              [t.pdfToPages, t.pdfToPagesDesc, !!selectedFile],
              [t.ocrExtraction, t.ocrExtractionDesc, isProcessing || !!preview],
              [t.textChunking, t.textChunkingDesc ?? "Text structuring", !!preview],
              [t.vectorIndexing, t.vectorIndexingDesc, false],
            ].map(([title, desc, active], i) => (
              <div key={i} className="flex gap-4">
                <div className="flex w-8 flex-col items-center">
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-[10px] ${
                      active
                        ? "border-[#2563ff] bg-[#2563ff] text-white"
                        : "border-slate-300 bg-white text-slate-400"
                    }`}
                  >
                    {i + 1}
                  </div>
                  {i !== 3 && <div className="mt-1 h-full w-px bg-slate-200" />}
                </div>

                <div className="flex-1 rounded-[18px] border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-[15px] font-bold text-[#0f172a]">{title as string}</p>
                  <p className="mt-1 text-[13px] text-[#64748b]">{desc as string}</p>
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-5 rounded-[16px] border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-700">
              {error}
            </div>
          )}

          {successMessage && (
            <div className="mt-5 rounded-[16px] border border-green-200 bg-green-50 px-4 py-3 text-[14px] text-green-700">
              {successMessage}
            </div>
          )}

          <div className="mt-6">
            <button
              onClick={handleStartProcessing}
              disabled={!selectedFile || isProcessing}
              className="w-full rounded-[18px] bg-[#2563ff] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)] disabled:opacity-60"
            >
              {renderProcessButtonText()}
            </button>
          </div>

          {preview && (
            <div className="mt-8 rounded-[22px] border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-[20px] font-extrabold text-[#0f172a]">
                Extracted Preview
              </h2>
              <p className="mt-2 text-[13px] text-[#64748b]">
                Review and edit the extracted fields before saving.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {[
                  ["document_type", "Document Type"],
                  ["order_id", "Order ID"],
                  ["flow_type", "Flow Type"],
                  ["company_name", "Company Name"],
                  ["supplier_name", "Supplier Name"],
                  ["date", "Date"],
                  ["currency", "Currency"],
                  ["raw_total_amount", "Raw Total Amount"],
                  ["final_total_amount", "Final Total Amount"],
                  ["payable_amount", "Payable Amount"],
                  ["cash_return", "Cash Return"],
                  ["received_status", "Received Status"],
                  ["paid_status", "Paid Status"],
                ].map(([field, label]) => (
                  <div key={field}>
                    <p className="mb-2 text-[12px] font-semibold text-[#64748b]">
                      {label}
                    </p>
                    {field === "flow_type" ? (
                      <select
                        value={(preview as any)[field] ?? ""}
                        onChange={(e) =>
                          handleFieldChange(field as keyof PreviewData, e.target.value)
                        }
                        className="w-full rounded-[14px] border border-slate-200 px-4 py-3 text-[14px] text-[#0f172a] outline-none focus:border-[#2563ff]"
                      >
                        <option value="">Select Flow Type</option>
                        <option value="payable">payable</option>
                        <option value="receivable">receivable</option>
                        <option value="income">income</option>
                        <option value="expense">expense</option>
                      </select>
                    ) : (
                      <input
                        value={String((preview as any)[field] ?? "")}
                        onChange={(e) =>
                          handleFieldChange(field as keyof PreviewData, e.target.value)
                        }
                        className="w-full rounded-[14px] border border-slate-200 px-4 py-3 text-[14px] text-[#0f172a] outline-none focus:border-[#2563ff]"
                      />
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-6">
                <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
                  Items
                </p>

                <div className="mt-3 space-y-3">
                  {preview.items && preview.items.length > 0 ? (
                    preview.items.map((item, index) => (
                      <div
                        key={index}
                        className="grid gap-3 rounded-[16px] border border-slate-200 p-4 sm:grid-cols-3"
                      >
                        <input
                          value={String(item.description ?? "")}
                          onChange={(e) =>
                            handleItemChange(index, "description", e.target.value)
                          }
                          placeholder="Description"
                          className="rounded-[12px] border border-slate-200 px-3 py-2 text-[14px] outline-none focus:border-[#2563ff]"
                        />
                        <input
                          value={String(item.quantity ?? "")}
                          onChange={(e) =>
                            handleItemChange(index, "quantity", e.target.value)
                          }
                          placeholder="Quantity"
                          className="rounded-[12px] border border-slate-200 px-3 py-2 text-[14px] outline-none focus:border-[#2563ff]"
                        />
                        <input
                          value={String(item.unit_price ?? "")}
                          onChange={(e) =>
                            handleItemChange(index, "unit_price", e.target.value)
                          }
                          placeholder="Unit Price"
                          className="rounded-[12px] border border-slate-200 px-3 py-2 text-[14px] outline-none focus:border-[#2563ff]"
                        />
                      </div>
                    ))
                  ) : (
                    <p className="text-[14px] text-[#64748b]">No items extracted.</p>
                  )}
                </div>
              </div>

              {showDuplicateWarning && (
                <div className="mt-6 rounded-[16px] border border-amber-200 bg-amber-50 px-4 py-3 text-[14px] text-amber-800">
                  <p className="font-semibold">{duplicateMessage}</p>
                  <p className="mt-1">
                    Existing Document ID: {existingDocumentId}
                  </p>

                  <div className="mt-3 flex gap-3">
                    <button
                      onClick={() => handleConfirmSave(true)}
                      disabled={isSaving}
                      className="rounded-xl bg-amber-500 px-4 py-2 text-white"
                    >
                      Save Anyway
                    </button>
                    <button
                      onClick={() => {
                        setShowDuplicateWarning(false);
                        setDuplicateMessage("");
                        setExistingDocumentId("");
                      }}
                      className="rounded-xl border border-amber-300 bg-white px-4 py-2 text-amber-800"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-6">
                <button
                  onClick={() => handleConfirmSave(false)}
                  disabled={isSaving}
                  className="w-full rounded-[18px] bg-[#16a34a] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(22,163,74,0.22)] disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Confirm and Save"}
                </button>
              </div>
            </div>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}