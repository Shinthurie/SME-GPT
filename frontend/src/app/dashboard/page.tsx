"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import BottomNav from "@/components/layout/BottomNav";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { getSession, logoutUser, SessionUser, getStoredToken } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { hasUnreadNotifications } from "@/lib/notifications";

const BACKEND_URL = "http://127.0.0.1:8000";

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
  const map: Record<DocIconType, { bg: string; color: string; icon: string }> = {
    invoice: { bg: "rgba(34,82,181,0.12)", color: "#2252b5", icon: "description" },
    po:      { bg: "rgba(124,58,237,0.10)", color: "#7c3aed", icon: "shopping_cart" },
    dn:      { bg: "rgba(249,115,22,0.10)", color: "#ea6c0a", icon: "local_shipping" },
    receipt: { bg: "rgba(22,163,74,0.10)",  color: "#16a34a", icon: "receipt" },
    unknown: { bg: "rgba(100,116,139,0.1)", color: "#64748b", icon: "draft" },
  };

  const item = map[type] ?? map.unknown;

  return (
    <div
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
      style={{ background: item.bg }}
    >
      <span className="material-symbols-outlined text-[20px]" style={{ color: item.color }}>
        {item.icon}
      </span>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      className="rounded-2xl px-4 py-4 shadow-sm"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
        {label}
      </p>
      <p
        className="mt-2 text-[22px] font-extrabold leading-none"
        style={{ color: color || "var(--text-1)" }}
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
  const [hasUnread, setHasUnread] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLang(getStoredLanguage());
      const s = await getSession();
      if (!s) { router.push("/login"); return; }
      setSession(s);

      try {
        const token = getStoredToken();
        if (!token) { setError("Missing login token. Please log in again."); return; }

        const res = await fetch(`${BACKEND_URL}/dashboard-summary`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });

        if (res.status === 401) {
          localStorage.removeItem("token");
          router.push("/login");
          return;
        }

        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || "Failed to fetch summary.");
        setSummary(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch dashboard summary.");
      }
    };

    load();
  }, [router]);

  useEffect(() => {
    const update = () => setHasUnread(hasUnreadNotifications());
    update();
    window.addEventListener("notifications-updated", update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener("notifications-updated", update);
      window.removeEventListener("storage", update);
    };
  }, []);

  if (!session) return null;

  const t = ui[lang];
  const recentDocs = summary?.recent_documents || [];

  const getRecentMeta = (doc: RecentDocument) => {
    const amt =
      doc.final_total_amount && doc.final_total_amount !== "NULL"
        ? `${doc.currency !== "NULL" ? doc.currency : "LKR"} ${doc.final_total_amount}`
        : "No Amount";
    const dt = doc.date && doc.date !== "NULL" ? doc.date : "No Date";
    return `${dt} • ${amt}`;
  };

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        {/* Header */}
        <header style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
            <div className="flex items-center gap-3">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl shadow-sm"
                style={{ background: "var(--brand)" }}
              >
                <span className="material-symbols-outlined text-[18px] text-white">receipt_long</span>
              </div>
              <div>
                <h1 className="text-[19px] font-extrabold tracking-tight text-[var(--text-1)]">
                  SME-GPT
                </h1>
                <p className="text-[12px] text-[var(--text-2)]">{session.companyName}</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <ThemeToggle />
              <LanguageSwitcher />

              <button
                onClick={() => router.push("/notifications")}
                className="relative flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-[var(--surface-2)]"
              >
                <span className="material-symbols-outlined text-[20px] text-[var(--text-2)]">
                  notifications
                </span>
                {hasUnread && (
                  <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
                )}
              </button>

              <button
                onClick={() => router.push("/profile")}
                className="flex h-9 w-9 items-center justify-center rounded-full text-white transition hover:opacity-90"
                style={{ background: "#c97b5a" }}
              >
                <span className="material-symbols-outlined text-[20px]">person</span>
              </button>

              <button
                onClick={async () => { await logoutUser(); router.push("/login"); }}
                className="rounded-xl px-3 py-1.5 text-[12px] font-semibold transition hover:bg-[var(--surface-2)]"
                style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">
          <section>
            <h2 className="text-[24px] font-extrabold tracking-tight text-[var(--text-1)] sm:text-[26px]">
              {t.welcomeTitle}
            </h2>
            <p className="mt-1.5 text-[13px] leading-6 text-[var(--text-2)]">
              {t.welcomeSubtitle}
            </p>
          </section>

          {error && (
            <div
              className="mt-4 rounded-2xl px-4 py-3 text-[13px] text-red-600"
              style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)" }}
            >
              {error}
            </div>
          )}

          {/* Upload CTA */}
          <section className="mt-6">
            <button
              onClick={() => router.push("/upload")}
              className="flex w-full items-center gap-4 rounded-2xl px-5 py-5 text-left text-white shadow-md transition hover:opacity-90 active:scale-[0.99]"
              style={{ background: "var(--brand)" }}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                <span className="material-symbols-outlined text-[22px]">upload_file</span>
              </div>
              <div>
                <p className="text-[15px] font-bold">{t.uploadCTA}</p>
                <p className="text-[12px] text-white/65">PDF, PNG, JPG supported</p>
              </div>
              <span className="material-symbols-outlined ml-auto text-white/50">chevron_right</span>
            </button>
          </section>

          {/* Stats */}
          <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label={t.totalDocs} value={String(summary?.total ?? 0)} />
            <StatCard label="Invoices" value={String(summary?.invoice ?? 0)} color="var(--brand-mid)" />
            <StatCard label="Receipts" value={String(summary?.receipt ?? 0)} color="#16a34a" />
            <StatCard label="PO" value={String(summary?.po ?? 0)} color="#7c3aed" />
            <StatCard label="DN" value={String(summary?.dn ?? 0)} color="#ea6c0a" />
          </section>

          {/* Recent docs */}
          <section className="mt-8">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[17px] font-extrabold tracking-tight text-[var(--text-1)]">
                {t.recentDocuments}
              </h3>
              <button
                onClick={() => router.push("/repository")}
                className="text-[13px] font-bold transition hover:opacity-75"
                style={{ color: "var(--brand-mid)" }}
              >
                {t.viewAll}
              </button>
            </div>

            <div className="space-y-3">
              {recentDocs.length === 0 ? (
                <div
                  className="rounded-2xl px-4 py-8 text-center text-[14px] text-[var(--text-2)]"
                  style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  No saved documents yet.
                </div>
              ) : (
                recentDocs.map((doc) => (
                  <button
                    key={doc.document_id}
                    onClick={() => router.push(`/analysis/${doc.document_id}`)}
                    className="w-full rounded-2xl p-4 text-left transition hover:-translate-y-px hover:shadow-md"
                    style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
                  >
                    <div className="flex items-center gap-4">
                      <DocIcon type={doc.document_type} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[15px] font-bold text-[var(--text-1)]">
                          {doc.document_id}
                        </p>
                        <p className="mt-0.5 text-[12px] text-[var(--text-2)]">
                          {getRecentMeta(doc)}
                        </p>
                      </div>
                      <span
                        className="shrink-0 rounded-lg px-2.5 py-1 text-[10px] font-bold uppercase"
                        style={{ background: "rgba(22,163,74,0.1)", color: "#16a34a" }}
                      >
                        ready
                      </span>
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
