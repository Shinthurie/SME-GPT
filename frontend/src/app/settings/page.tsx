"use client";
// Settings page: IT-46 (Budget), IT-47 (Audit Pack), IT-48 (Monthly Email), IT-49 (WhatsApp)

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import ThemeToggle from "@/components/layout/ThemeToggle";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getStoredLanguage, AppLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || sessionStorage.getItem("token") || "";
}

const BUDGET_CATS = ["Transport","Food","Supplies","Utilities","Services","Rent","Marketing","Other"];
const PERIOD_OPTIONS = [
  { key: "this_week",   en: "This Week",   si: "මේ සතිය"     },
  { key: "this_month",  en: "This Month",  si: "මේ මාසය"     },
  { key: "last_month",  en: "Last Month",  si: "ගිය මාසය"    },
  { key: "this_year",   en: "This Year",   si: "මේ අවුරුද්ද" },
  { key: "custom",      en: "Custom Range", si: "අභිමත"       },
];

export default function SettingsPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");

  // Budget state
  const [budgetEnabled, setBudgetEnabled] = useState(false);
  const [budgets, setBudgets]             = useState<Record<string,string>>({});
  const [budgetSaved, setBudgetSaved]     = useState(false);

  // Audit Pack state
  const [period, setPeriod]               = useState("this_month");
  const [customFrom, setCustomFrom]       = useState("");
  const [customTo, setCustomTo]           = useState("");
  const [exporting, setExporting]         = useState(false);

  // WhatsApp state
  const [phoneNumber, setPhoneNumber]     = useState("");
  const [phoneSaved, setPhoneSaved]       = useState(false);

  // Monthly email toggle
  const [monthlyEmail, setMonthlyEmail]   = useState(false);

  useEffect(() => {
    setLang(getStoredLanguage());
    const token = getToken();
    if (!token) { router.push("/login"); return; }
    // Load saved budgets
    fetch(`${BACKEND_URL}/user/budget-settings`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => {
        if (d.budgets && Object.keys(d.budgets).length > 0) {
          setBudgetEnabled(true);
          setBudgets(d.budgets);
        }
      }).catch(() => {});
    // Load stored phone (from profile)
    const session = localStorage.getItem("sme_gpt_session");
    if (session) {
      try { setPhoneNumber(JSON.parse(session)?.phoneNumber || ""); } catch {}
    }
  }, []);

  const saveBudgets = async () => {
    const token = getToken();
    await fetch(`${BACKEND_URL}/user/budget-settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ budgets: budgetEnabled ? budgets : {} }),
    });
    setBudgetSaved(true);
    setTimeout(() => setBudgetSaved(false), 2500);
  };

  const downloadAuditPack = async () => {
    setExporting(true);
    const token = getToken();
    try {
      const body: Record<string, string> = { period };
      if (period === "custom") { body.date_from = customFrom; body.date_to = customTo; }
      const res = await fetch(`${BACKEND_URL}/reports/audit-pack`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) { alert("Export failed"); return; }
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = `audit_pack_${period}.zip`; a.click();
      URL.revokeObjectURL(url);
    } finally { setExporting(false); }
  };

  const t = ui[lang];

  return (
    <MobileShell>
      <div className="min-h-screen pb-24" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[720px] px-4 py-6 sm:px-6">

          {/* Header */}
          <div className="mb-5 flex items-center justify-between">
            <button onClick={() => router.back()}
              className="flex items-center gap-1.5 text-[13px] font-semibold hover:opacity-75 transition"
              style={{ color: "var(--brand-mid)" }}>
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              {t.backToDashboard}
            </button>
            <div className="flex items-center gap-2"><ThemeToggle /><LanguageSwitcher /></div>
          </div>

          <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)]">
            {lang === "si" ? "සැකසීම්" : "Settings"}
          </h1>
          <p className="mt-1 text-[13px] text-[var(--text-2)]">
            {lang === "si" ? "ඔබගේ SME-GPT අකවුන්ටය සකස් කරන්න" : "Configure your SME-GPT account preferences."}
          </p>

          <div className="mt-6 space-y-5">

            {/* ── IT-46: Budget vs Actual ──────────────────────────────── */}
            <section className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[15px] font-bold text-[var(--text-1)]">
                    {lang === "si" ? "මාසික අයවැය" : "Monthly Budget Tracker"}
                  </p>
                  <p className="text-[12px] text-[var(--text-2)]">
                    {lang === "si" ? "කාණ්ඩ අනුව ඉලක්ක නියම කරන්න"
                      : "Set monthly spending targets per category. A comparison widget appears on your dashboard."}
                  </p>
                </div>
                <button onClick={() => setBudgetEnabled(b => !b)}
                  className="relative h-6 w-11 rounded-full transition"
                  style={{ background: budgetEnabled ? "var(--brand-mid)" : "#d1d5db" }}>
                  <span className="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform"
                    style={{ transform: budgetEnabled ? "translateX(20px)" : "none" }} />
                </button>
              </div>

              {budgetEnabled && (
                <div className="mt-4 space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {BUDGET_CATS.map(cat => (
                      <div key={cat} className="flex items-center gap-3 rounded-xl border px-4 py-2.5"
                        style={{ background: "var(--bg)", borderColor: "var(--border)" }}>
                        <span className="flex-1 text-[13px] text-[var(--text-1)]">{cat}</span>
                        <span className="text-[12px] text-[var(--text-3)]">LKR</span>
                        <input type="number" min="0" value={budgets[cat] || ""}
                          onChange={e => setBudgets(b => ({ ...b, [cat]: e.target.value }))}
                          placeholder="0"
                          className="w-24 bg-transparent text-right text-[13px] font-bold text-[var(--text-1)] outline-none" />
                      </div>
                    ))}
                  </div>
                  <button onClick={saveBudgets}
                    className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-bold text-white transition hover:opacity-90"
                    style={{ background: "var(--brand-mid)" }}>
                    <span className="material-symbols-outlined text-[16px]">save</span>
                    {budgetSaved
                      ? (lang === "si" ? "සුරකිනු ලැබිණි ✓" : "Saved ✓")
                      : (lang === "si" ? "සුරකින්න" : "Save Budgets")}
                  </button>
                </div>
              )}
            </section>

            {/* ── IT-47: Audit Pack Export ─────────────────────────────── */}
            <section className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-[15px] font-bold text-[var(--text-1)]">
                {lang === "si" ? "විගණන ඇසුරුම" : "Audit Pack Export"}
              </p>
              <p className="mt-0.5 text-[12px] text-[var(--text-2)]">
                {lang === "si"
                  ? "ඔබ ඇති කාලසීමාව සඳහා සියලු ලේඛන + Excel + JSON ZIP ලෙස."
                  : "Download all documents for a period as a ZIP containing images, Excel ledger, and JSON summary."}
              </p>
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap gap-2">
                  {PERIOD_OPTIONS.map(p => (
                    <button key={p.key} onClick={() => setPeriod(p.key)}
                      className="rounded-xl px-4 py-2 text-[12px] font-semibold transition"
                      style={period === p.key
                        ? { background: "#2252b5", color: "#fff" }
                        : { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
                      {lang === "si" ? p.si : p.en}
                    </button>
                  ))}
                </div>
                {period === "custom" && (
                  <div className="flex items-center gap-3">
                    <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)}
                      className="rounded-xl border px-3 py-2 text-[13px]"
                      style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                    <span className="text-[12px] text-[var(--text-3)]">{lang === "si" ? "සිට" : "to"}</span>
                    <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)}
                      className="rounded-xl border px-3 py-2 text-[13px]"
                      style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                  </div>
                )}
                <button onClick={downloadAuditPack} disabled={exporting}
                  className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-bold text-white transition disabled:opacity-60 hover:opacity-90"
                  style={{ background: "#16a34a" }}>
                  {exporting
                    ? <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
                    : <span className="material-symbols-outlined text-[16px]">download</span>}
                  {exporting
                    ? (lang === "si" ? "සකස් කරමින්..." : "Generating…")
                    : (lang === "si" ? "ZIP බාගන්න" : "Download ZIP")}
                </button>
              </div>
            </section>

            {/* ── IT-48: Monthly P&L Email ─────────────────────────────── */}
            <section className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[15px] font-bold text-[var(--text-1)]">
                    {lang === "si" ? "මාසික P&L ඊමේල්" : "Monthly P&L Email"}
                  </p>
                  <p className="text-[12px] text-[var(--text-2)]">
                    {lang === "si"
                      ? "සෑම මාසයේ 1 වැනිදා ඔබේ ලාභ / පාඩු සාරාංශය ඊමේල් ලෙස ලැබේ."
                      : "Receive a profit & loss summary email on the 1st of every month. Requires SMTP configuration in backend/.env."}
                  </p>
                </div>
                <button onClick={() => setMonthlyEmail(m => !m)}
                  className="relative h-6 w-11 rounded-full transition"
                  style={{ background: monthlyEmail ? "var(--brand-mid)" : "#d1d5db" }}>
                  <span className="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform"
                    style={{ transform: monthlyEmail ? "translateX(20px)" : "none" }} />
                </button>
              </div>
              {monthlyEmail && (
                <div className="mt-3 rounded-xl px-4 py-3 text-[12px]"
                  style={{ background: "rgba(34,82,181,0.06)", border: "1px solid rgba(34,82,181,0.15)", color: "#2252b5" }}>
                  <p className="font-semibold">{lang === "si" ? "ක‍ාර්යසාධනය:" : "To enable:"}</p>
                  <p className="mt-1">Set <code>MONTHLY_EMAIL_ENABLED=true</code> in <code>backend/.env</code> and restart the backend. The scheduler runs at 08:00 on the 1st.</p>
                </div>
              )}
            </section>

            {/* ── IT-49: WhatsApp Integration ──────────────────────────── */}
            <section className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-[15px] font-bold text-[var(--text-1)]">
                {lang === "si" ? "WhatsApp ඒකාබද්ධතාව" : "WhatsApp Bill Forwarding"}
              </p>
              <p className="mt-0.5 text-[12px] text-[var(--text-2)]">
                {lang === "si"
                  ? "WhatsApp හරහා ලැබෙන රිසිට් ඡායාරූප ස්වයංක‍ීයව ගබඩා කළ හැකිය."
                  : "Forward bill photos from WhatsApp to your SME-GPT number — they appear in the repository automatically."}
              </p>
              <div className="mt-4 space-y-3">
                <div>
                  <label className="mb-1.5 block text-[12px] font-semibold text-[var(--text-2)]">
                    {lang === "si" ? "ඔබගේ WhatsApp අංකය (ලේඛන ගනු ලැබේ)" : "Your WhatsApp Number (bills forwarded from this number)"}
                  </label>
                  <input value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)}
                    placeholder="+94771234567"
                    className="w-full rounded-xl border px-4 py-2.5 text-[13px]"
                    style={{ background: "var(--bg)", borderColor: "var(--border)", color: "var(--text-1)" }} />
                </div>
                <div className="rounded-xl px-4 py-3 text-[12px]"
                  style={{ background: "rgba(22,163,74,0.06)", border: "1px solid rgba(22,163,74,0.2)", color: "#16a34a" }}>
                  <p className="font-semibold">{lang === "si" ? "සැකසීම:" : "Setup steps:"}</p>
                  <ol className="mt-1 list-decimal list-inside space-y-1 opacity-90">
                    <li>Create a Twilio account at twilio.com</li>
                    <li>Get a WhatsApp-enabled number from Twilio Sandbox</li>
                    <li>Set webhook URL: <code>POST https://your-server/webhook/whatsapp</code></li>
                    <li>Add <code>TWILIO_AUTH_TOKEN</code> + <code>TWILIO_ACCOUNT_SID</code> to backend/.env</li>
                    <li>Save your phone number above so SME-GPT can match incoming messages to your account</li>
                  </ol>
                </div>
                {phoneSaved && (
                  <p className="text-[12px] font-bold text-green-600">
                    {lang === "si" ? "සුරකිනු ලැබිණි ✓" : "Phone number saved ✓"}
                  </p>
                )}
              </div>
            </section>

          </div>
        </main>
        <BottomNav />
      </div>
    </MobileShell>
  );
}
