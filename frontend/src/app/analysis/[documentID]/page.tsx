"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage } from "@/lib/i18n";

const BACKEND_URL ="http://127.0.0.1:8000";

type Item = {
  description: string;
  quantity: string | number;
  unit_price: string | number;
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
  currency: string;
  status: string;
  language: string;
  order_id: string;
  flow_type: string;
  received_status: string;
  paid_status: string;
  items: Item[];
  image_url?: string | null;
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
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
      } catch (err: any) {
        setError(err.message || "Failed to load document.");
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [documentId, router]);

  const formatParty = () => {
    if (!document) return "NULL";
    if (document.company_name && document.company_name !== "NULL") return document.company_name;
    if (document.supplier_name && document.supplier_name !== "NULL") return document.supplier_name;
    return "NULL";
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
              <button className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#2563ff] transition hover:bg-[#eef4ff]">
                <span className="material-symbols-outlined">share</span>
              </button>
              <button className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#2563ff] transition hover:bg-[#eef4ff]">
                <span className="material-symbols-outlined">more_vert</span>
              </button>
            </div>
          </div>

          <div className="mb-5">
            <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
              {loading ? "Loading..." : document?.document_id || "Document"}
            </h1>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Financial Document Analysis
            </p>
          </div>

          {loading ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              Loading document...
            </div>
          ) : error ? (
            <div className="rounded-[18px] border border-red-200 bg-red-50 p-6 text-center text-[14px] text-red-700">
              {error}
            </div>
          ) : !document ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              Document not found.
            </div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
              <div className="rounded-[20px] bg-[#eef2f7] p-3 shadow-sm">
                <div className="rounded-[16px] bg-white p-3">
                  <div className="flex min-h-[420px] items-center justify-center rounded-[16px] bg-[#f3f4f6] sm:min-h-[520px]">
                    {document.image_url ? (
                      <img
                        src={`${BACKEND_URL}${document.image_url}`}
                        alt={document.document_id}
                        className="max-h-[520px] w-full rounded-[12px] object-contain"
                      />
                    ) : (
                      <div className="text-[13px] text-[#94a3b8]">
                        No saved preview image for this document
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <div className="rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <h2 className="text-[18px] font-extrabold text-[#0f172a] sm:text-[20px]">
                      Document Detail
                    </h2>

                    <div className="flex items-center gap-2">
                      <span className="rounded-xl bg-[#eef4ff] px-3 py-2 text-[12px] font-semibold text-[#2563ff]">
                        {document.document_type?.toUpperCase() || "UNKNOWN"}
                      </span>
                      <span className="rounded-xl bg-[#f1f5f9] px-3 py-2 text-[12px] text-[#334155]">
                        {document.currency || "NULL"}
                      </span>
                      <span className="rounded-xl bg-[#dcfce7] px-3 py-2 text-[12px] font-semibold text-[#16a34a]">
                        {document.status || "ready"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-4">
                  <InfoCard title="Metadata">
                    <span className="font-semibold text-[#0f172a]">Document ID:</span> {document.document_id}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Order ID:</span> {document.order_id || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Date:</span> {document.date || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Party:</span> {formatParty()}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Flow Type:</span> {document.flow_type || "NULL"}
                  </InfoCard>

                  <InfoCard title="Financial Summary">
                    <span className="font-semibold text-[#0f172a]">Raw Total:</span> {document.raw_total_amount || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Final Total:</span> {document.final_total_amount || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Payable Amount:</span> {document.payable_amount || "NULL"}
                  </InfoCard>

                  <InfoCard title="Status">
                    <span className="font-semibold text-[#0f172a]">Received Status:</span> {document.received_status || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Paid Status:</span> {document.paid_status || "NULL"}
                    <br />
                    <span className="font-semibold text-[#0f172a]">Language:</span> {document.language || "NULL"}
                  </InfoCard>

                  <div className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
                    <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#64748b]">
                      Items
                    </p>

                    <div className="mt-3 space-y-3">
                      {document.items && document.items.length > 0 ? (
                        document.items.map((item, index) => (
                          <div
                            key={index}
                            className="grid gap-2 rounded-[12px] border border-slate-200 p-3 sm:grid-cols-3"
                          >
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">Description:</span> {item.description || "NULL"}
                            </div>
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">Quantity:</span> {item.quantity ?? "NULL"}
                            </div>
                            <div className="text-[14px] text-[#0f172a]">
                              <span className="font-semibold">Unit Price:</span> {item.unit_price ?? "NULL"}
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-[14px] text-[#64748b]">No items available.</p>
                      )}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => router.push("/repository")}
                  className="mt-5 w-full rounded-[18px] bg-[#2563ff] py-4 text-[15px] font-bold text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)]"
                >
                  Back to Repository
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