"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage } from "@/lib/i18n";

const BACKEND_URL ="http://127.0.0.1:8000";

type RepoDocument = {
  document_id: string;
  document_type: "invoice" | "po" | "dn" | "receipt" | "unknown";
  company_name: string;
  supplier_name: string;
  date: string;
  final_total_amount: string;
  currency: string;
  status: string;
};

type TabType = "all" | "invoice" | "po" | "dn" | "receipt";

function getAuthToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

function TypeIcon({ type }: { type: RepoDocument["document_type"] }) {
  const map = {
    invoice: {
      bg: "bg-[#eaf0ff]",
      color: "text-[#2563ff]",
      icon: "description",
    },
    po: {
      bg: "bg-[#f3e8ff]",
      color: "text-[#9333ea]",
      icon: "shopping_cart",
    },
    dn: {
      bg: "bg-[#fff7ed]",
      color: "text-[#f97316]",
      icon: "local_shipping",
    },
    receipt: {
      bg: "bg-[#e7f4ea]",
      color: "text-[#16a34a]",
      icon: "receipt_long",
    },
    unknown: {
      bg: "bg-slate-100",
      color: "text-slate-500",
      icon: "draft",
    },
  };

  const item = map[type] || map.unknown;

  return (
    <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${item.bg} ${item.color}`}>
      <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
    </div>
  );
}

export default function RepositoryPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [tab, setTab] = useState<TabType>("all");
  const [documents, setDocuments] = useState<RepoDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLang(getStoredLanguage());
  }, []);

  useEffect(() => {
    const fetchDocuments = async () => {
      const token = getAuthToken();

      if (!token) {
        setError("Login token missing. Please log in again.");
        setLoading(false);
        router.push("/login");
        return;
      }

      try {
        const res = await fetch(`${BACKEND_URL}/documents`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          cache: "no-store",
        });

        if (res.status === 401) {
          localStorage.removeItem("token");
          sessionStorage.removeItem("token");
          router.push("/login");
          return;
        }

        const data = await res.json();

        if (!res.ok || !data.success) {
          throw new Error(data.message || "Failed to fetch documents.");
        }

        setDocuments(data.documents || []);
      } catch (fetchError: any) {
        console.error("Failed to fetch documents:", fetchError);
        setError(fetchError.message || "Failed to fetch documents.");
      } finally {
        setLoading(false);
      }
    };

    fetchDocuments();
  }, [router]);

  const filteredItems = useMemo(() => {
    if (tab === "all") return documents;
    return documents.filter((item) => item.document_type === tab);
  }, [tab, documents]);

  const tabLabel = (value: TabType) => {
    if (lang === "si") {
      if (value === "all") return "සියල්ල";
      if (value === "invoice") return "ඉන්වොයිස්";
      if (value === "po") return "PO";
      if (value === "dn") return "DN";
      return "රිසිට්";
    }

    if (value === "all") return "All";
    if (value === "invoice") return "Invoice";
    if (value === "po") return "PO";
    if (value === "dn") return "DN";
    return "Receipt";
  };

  const topSubtitle =
    lang === "si" ? "SME-ව්‍යාපාර ලේඛන" : "SME business documents";

  const formatAmount = (item: RepoDocument) => {
    if (!item.final_total_amount || item.final_total_amount === "NULL") {
      return "No Amount";
    }

    const currency = item.currency && item.currency !== "NULL" ? item.currency : "LKR";
    return `${currency} ${item.final_total_amount}`;
  };

  const getPartyName = (item: RepoDocument) => {
    if (item.company_name && item.company_name !== "NULL") return item.company_name;
    if (item.supplier_name && item.supplier_name !== "NULL") return item.supplier_name;
    return "Unknown Party";
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[920px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
                Repository
              </h1>
              <p className="mt-1 text-[12px] text-[#94a3b8]">{topSubtitle}</p>
            </div>

            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <button className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-[#64748b] shadow-sm">
                <span className="material-symbols-outlined text-[20px]">search</span>
              </button>
              <button
                onClick={() => router.push("/upload")}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-[#2563ff] text-white shadow-sm"
              >
                <span className="material-symbols-outlined text-[22px]">add</span>
              </button>
            </div>
          </div>

          <div className="mb-5 flex flex-wrap gap-2">
            {(["all", "invoice", "po", "dn", "receipt"] as TabType[]).map((value) => (
              <button
                key={value}
                onClick={() => setTab(value)}
                className={`rounded-full px-4 py-2 text-[12px] font-semibold transition ${
                  tab === value
                    ? "bg-[#2563ff] text-white shadow-sm"
                    : "border border-slate-200 bg-white text-[#64748b]"
                }`}
              >
                {tabLabel(value)}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              Loading documents...
            </div>
          ) : error ? (
            <div className="rounded-[18px] border border-red-200 bg-red-50 p-6 text-center text-[14px] text-red-700">
              {error}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b]">
              No documents found.
            </div>
          ) : (
            <div className="space-y-4">
              {filteredItems.map((item) => (
                <div
                  key={item.document_id}
                  className="rounded-[18px] border border-slate-200 bg-white p-4 shadow-[0_2px_10px_rgba(15,23,42,0.05)]"
                >
                  <div className="flex items-start gap-4">
                    <TypeIcon type={item.document_type} />

                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#94a3b8]">
                        {item.document_type === "invoice"
                          ? "INVOICE"
                          : item.document_type === "po"
                          ? "PURCHASE ORDER"
                          : item.document_type === "dn"
                          ? "DELIVERY NOTE"
                          : item.document_type === "receipt"
                          ? "RECEIPT"
                          : "DOCUMENT"}
                      </p>

                      <p className="mt-1 text-[15px] font-bold leading-tight text-[#0f172a] sm:text-[16px]">
                        {item.document_id}
                      </p>

                      <div className="mt-2 grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-[11px] text-[#94a3b8]">
                            {item.document_type === "po"
                              ? "Client"
                              : item.document_type === "dn"
                              ? "Receiver"
                              : "Vendor"}
                          </p>
                          <p className="text-[13px] text-[#334155]">{getPartyName(item)}</p>
                        </div>

                        <div className="sm:text-right">
                          <p className="text-[11px] text-[#94a3b8]">Date</p>
                          <p className="text-[13px] text-[#334155]">
                            {item.date && item.date !== "NULL" ? item.date : "No Date"}
                          </p>
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-4">
                        <span className="inline-flex rounded-xl bg-[#dcfce7] px-3 py-1.5 text-[10px] font-bold uppercase text-[#16a34a]">
                          ready
                        </span>

                        <button
                          onClick={() => router.push(`/analysis/${item.document_id}`)}
                          className="text-[12px] font-bold text-[#2563ff]"
                        >
                          OPEN
                        </button>
                      </div>
                    </div>

                    <div className="text-right">
                      <p
                        className={`text-[13px] font-bold ${
                          formatAmount(item) === "No Amount" ? "text-[#94a3b8]" : "text-[#0f172a]"
                        }`}
                      >
                        {formatAmount(item)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}