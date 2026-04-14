"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import BottomNav from "@/components/layout/BottomNav";
import { getSession, logoutUser, SessionUser, getStoredToken } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL ="http://127.0.0.1:8000";

type SummaryData = {
  total: number;
  invoice: number;
  receipt: number;
  po: number;
  dn: number;
  recent_documents: RecentDocument[];
};

type RecentDocument = {
  document_id: string;
  document_type: "invoice" | "po" | "dn" | "receipt" | "unknown";
  company_name: string;
  supplier_name: string;
  date: string;
  final_total_amount: string;
  currency: string;
};

type DocIconType = "po" | "invoice" | "dn" | "receipt" | "unknown";

function DocIcon({ type }: { type: DocIconType }) {
  if (type === "po") {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#f5efdc]">
        <span className="material-symbols-outlined text-[20px] text-[#d97706]">
          receipt_long
        </span>
      </div>
    );
  }

  if (type === "invoice") {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#eaf0ff]">
        <span className="material-symbols-outlined text-[20px] text-[#2563ff]">
          description
        </span>
      </div>
    );
  }

  if (type === "dn") {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#fff7ed]">
        <span className="material-symbols-outlined text-[20px] text-[#f97316]">
          local_shipping
        </span>
      </div>
    );
  }

  if (type === "receipt") {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#e7f4ea]">
        <span className="material-symbols-outlined text-[20px] text-[#16a34a]">
          receipt
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
      <span className="material-symbols-outlined text-[20px] text-slate-500">
        draft
      </span>
    </div>
  );
}

function StatCard({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="rounded-[18px] border border-slate-200 bg-white px-4 py-4 shadow-[0_2px_10px_rgba(15,23,42,0.05)]">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#94a3b8]">
        {label}
      </p>
      <p
        className="mt-2 text-[20px] font-extrabold leading-none"
        style={{ color: valueColor || "#0f172a" }}
      >
        {value}
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<SessionUser | null>(null);
  const [lang, setLang] = useState<AppLanguage>("en");
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLang(getStoredLanguage());

      const currentSession = await getSession();

      if (!currentSession) {
        router.push("/login");
        return;
      }

      setSession(currentSession);

      try {
        const token = getStoredToken();

        if (!token) {
          setError("Missing login token. Please log in again.");
          return;
        }

        const res = await fetch(`${BACKEND_URL}/dashboard-summary`, {
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
          throw new Error(data.message || "Failed to fetch dashboard summary.");
        }

        setSummary(data);
      } catch (fetchError: any) {
        console.error("Failed to fetch dashboard summary:", fetchError);
        setError(fetchError.message || "Failed to fetch dashboard summary.");
      }
    };

    load();
  }, [router]);

  if (!session) return null;

  const t = ui[lang];
  const recentDocuments = summary?.recent_documents || [];

  const getRecentMeta = (doc: RecentDocument) => {
    const amount =
      doc.final_total_amount && doc.final_total_amount !== "NULL"
        ? `${doc.currency !== "NULL" ? doc.currency : "LKR"} ${doc.final_total_amount}`
        : "No Amount";

    const docDate = doc.date && doc.date !== "NULL" ? doc.date : "No Date";

    return `${docDate} • ${amount}`;
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#2563ff] text-white shadow-sm">
                <span className="material-symbols-outlined text-[20px]">
                  receipt_long
                </span>
              </div>

              <div>
                <h1 className="text-[20px] font-extrabold tracking-tight text-[#0f172a]">
                  SME-GPT
                </h1>
                <p className="text-[12px] text-[#64748b]">
                  {session.companyName}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <LanguageSwitcher />

              <button className="flex h-10 w-10 items-center justify-center rounded-full bg-[#eef2f7] text-[#475569] transition hover:bg-[#e6ebf2]">
                <span className="material-symbols-outlined text-[18px]">
                  notifications
                </span>
              </button>

              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f7b092] text-white shadow-sm">
                <span className="material-symbols-outlined text-[18px]">
                  person
                </span>
              </div>

              <button
                onClick={async () => {
                  await logoutUser();
                  router.push("/login");
                }}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-[#64748b] transition hover:bg-slate-50"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">
          <section>
            <h2 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
              {t.welcomeTitle}
            </h2>
            <p className="mt-2 text-[13px] leading-7 text-[#64748b] sm:text-[14px]">
              {t.welcomeSubtitle}
            </p>
          </section>

          {error ? (
            <div className="mt-4 rounded-[16px] border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-700">
              {error}
            </div>
          ) : null}

          <section className="mt-6">
            <button
              onClick={() => router.push("/upload")}
              className="flex w-full items-center gap-4 rounded-[18px] bg-[#2563ff] px-5 py-5 text-left text-white shadow-[0_10px_24px_rgba(37,99,255,0.22)] transition hover:translate-y-[1px] hover:opacity-95"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                <span className="material-symbols-outlined text-[22px]">
                  upload_file
                </span>
              </div>
              <span className="text-[15px] font-bold leading-7">
                {t.uploadCTA}
              </span>
            </button>
          </section>

          <section className="mt-8 grid gap-3 sm:grid-cols-3">
            <StatCard label={t.totalDocs} value={String(summary?.total ?? 0)} />
            <StatCard
              label="Invoices"
              value={String(summary?.invoice ?? 0)}
              valueColor="#2563ff"
            />
            <StatCard
              label="Receipts"
              value={String(summary?.receipt ?? 0)}
              valueColor="#16a34a"
            />
          </section>

          <section className="mt-3 grid gap-3 sm:grid-cols-2">
            <StatCard
              label="PO"
              value={String(summary?.po ?? 0)}
              valueColor="#9333ea"
            />
            <StatCard
              label="DN"
              value={String(summary?.dn ?? 0)}
              valueColor="#f97316"
            />
          </section>

          <section className="mt-8">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[18px] font-extrabold tracking-tight text-[#0f172a]">
                {t.recentDocuments}
              </h3>
              <button
                onClick={() => router.push("/repository")}
                className="text-[13px] font-bold text-[#2563ff] transition hover:opacity-80"
              >
                {t.viewAll}
              </button>
            </div>

            <div className="space-y-4">
              {recentDocuments.length === 0 ? (
                <div className="rounded-[20px] border border-slate-200 bg-white px-4 py-6 text-center text-[14px] text-[#64748b] shadow-[0_2px_10px_rgba(15,23,42,0.05)]">
                  No saved documents yet.
                </div>
              ) : (
                recentDocuments.map((doc) => (
                  <button
                    key={doc.document_id}
                    onClick={() => router.push(`/analysis/${doc.document_id}`)}
                    className="w-full rounded-[20px] border border-slate-200 bg-white px-4 py-4 text-left shadow-[0_2px_10px_rgba(15,23,42,0.05)] transition hover:-translate-y-[1px] hover:shadow-md"
                  >
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                      <DocIcon type={doc.document_type} />

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[15px] font-bold tracking-tight text-[#0f172a] sm:text-[16px]">
                          {doc.document_id}
                        </p>
                        <p className="mt-1 text-[12px] text-[#64748b] sm:text-[13px]">
                          {getRecentMeta(doc)}
                        </p>
                      </div>

                      <div className="text-left sm:text-right">
                        <span className="inline-flex rounded-xl bg-[#dcfce7] px-3 py-1.5 text-[10px] font-bold uppercase text-[#16a34a]">
                          ready
                        </span>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}