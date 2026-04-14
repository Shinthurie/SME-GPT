"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession, loginUser } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();

  const [lang, setLang] = useState<AppLanguage>("en");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const checkSession = async () => {
      setLang(getStoredLanguage());
      const session = await getSession();

      if (session) {
        router.push("/dashboard");
      }
    };

    checkSession();
  }, [router]);

  const t = ui[lang];

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    const result = await loginUser(email, password);

    if (!result.ok) {
      setError(result.data?.error || t.invalidLogin);
      return;
    }

    if (result.data?.requiresTwoFactor) {
      router.push(`/login/verify?token=${result.data.verificationToken}`);
      return;
    }

    if (result.data?.success) {
      if (result.data.token) {
        localStorage.setItem("token", result.data.token);
      } else {
        setError("Login token not received. Please try again.");
        return;
      }

      router.push("/dashboard");
      return;
    }

    setError("Login failed.");
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f7f8fb] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
        <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[1280px] items-center">
          <div className="grid w-full items-center gap-8 lg:grid-cols-[520px_minmax(0,1fr)] xl:grid-cols-[560px_minmax(0,1fr)]">
            <div
              className="w-full rounded-[30px] border border-[#d9dff0] bg-[#f7f8fb] px-5 py-8 shadow-[0_0_0_2px_rgba(88,114,255,0.08)] sm:px-8 sm:py-10"
              style={{
                backgroundImage: `
                  linear-gradient(rgba(30,41,59,0.05) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(30,41,59,0.05) 1px, transparent 1px)
                `,
                backgroundSize: "56px 56px",
                backgroundPosition: "center center",
              }}
            >
              <div className="mb-4 flex justify-end">
                <LanguageSwitcher />
              </div>

              <div className="mx-auto flex max-w-[390px] flex-col">
                <div className="mx-auto mb-5 flex h-[54px] w-[54px] items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="material-symbols-outlined text-[24px] text-[#4d7cff]">
                    account_tree
                  </span>
                </div>

                <h1 className="text-center text-[28px] font-extrabold tracking-tight text-[#0f172a] sm:text-[32px]">
                  {t.appName}
                </h1>

                <p className="mt-2 text-center text-[11px] font-bold uppercase tracking-[0.18em] text-[#8a96ab]">
                  Secure AI Workspace
                </p>

                <form onSubmit={handleLogin} className="mt-10 space-y-5">
                  <div>
                    <label className="mb-2 block text-[10px] font-bold uppercase tracking-[0.12em] text-[#7e8aa2]">
                      {t.businessEmail}
                    </label>
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[18px] text-[#93a0b5]">
                        business_center
                      </span>
                      <input
                        type="email"
                        placeholder="name@company.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white pl-12 pr-4 text-[15px] text-slate-900 shadow-[0_4px_14px_rgba(15,23,42,0.04)] outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-[10px] font-bold uppercase tracking-[0.12em] text-[#7e8aa2]">
                      {t.password}
                    </label>
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[18px] text-[#93a0b5]">
                        shield_lock
                      </span>
                      <input
                        type="password"
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white pl-12 pr-4 text-[15px] text-slate-900 shadow-[0_4px_14px_rgba(15,23,42,0.04)] outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                        required
                      />
                    </div>

                    <div className="mt-2 flex justify-end">
                      <button
                        type="button"
                        onClick={() => router.push("/forgot-password")}
                        className="text-[11px] font-semibold text-[#4d7cff] transition hover:opacity-80"
                      >
                        {t.forgotAccess}
                      </button>
                    </div>
                  </div>

                  {error && (
                    <p className="text-[12px] font-medium text-red-600">
                      {error}
                    </p>
                  )}

                  <button
                    type="submit"
                    className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#07122f] text-[16px] font-bold text-white shadow-[0_10px_25px_rgba(7,18,47,0.22)] transition hover:translate-y-[1px] hover:opacity-95"
                  >
                    <span>{t.signIn}</span>
                    <span className="material-symbols-outlined text-[18px]">
                      login
                    </span>
                  </button>
                </form>

                <div className="mt-8 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-[#e1e6f2] bg-white px-3 py-4 text-center shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
                    <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-xl bg-[#edf3ff]">
                      <span className="material-symbols-outlined text-[18px] text-[#4d7cff]">
                        description
                      </span>
                    </div>
                    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.08em] text-[#556277]">
                      {t.uploadFeature}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-[#e1e6f2] bg-white px-3 py-4 text-center shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
                    <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-xl bg-[#edf3ff]">
                      <span className="material-symbols-outlined text-[18px] text-[#4d7cff]">
                        translate
                      </span>
                    </div>
                    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.08em] text-[#556277]">
                      {t.languageFeature}
                    </p>
                  </div>
                </div>

                <p className="mt-5 text-center text-[11px] italic leading-5 text-[#9aa5b6]">
                  {t.authCaption}
                </p>

                <div className="mt-6 text-center">
                  <p className="text-[12px] text-[#7e8aa2]">
                    {t.noAccount}{" "}
                    <a href="/signup" className="font-bold text-[#4d7cff]">
                      {t.signUp}
                    </a>
                  </p>
                </div>
              </div>
            </div>

            <div className="hidden h-full lg:flex lg:items-center">
              <div className="w-full rounded-[30px] border border-[#d9dff0] bg-white p-8 xl:p-10 shadow-sm">
                <h2 className="text-4xl font-extrabold tracking-tight text-[#0f172a]">
                  SME-GPT
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[#64748b]">
                  Intelligent OCR, bilingual extraction, financial document analysis,
                  discrepancy detection, and explainable AI for invoices, POs, and related records.
                </p>

                <div className="mt-10 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-3xl bg-[#eef4ff] p-6">
                    <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#2563ff]">
                      OCR + NLP
                    </p>
                    <p className="mt-3 text-[#475569]">
                      Extract, structure, validate, and query financial documents in one workspace.
                    </p>
                  </div>

                  <div className="rounded-3xl bg-[#f8fafc] p-6">
                    <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#2563ff]">
                      Bilingual Ready
                    </p>
                    <p className="mt-3 text-[#475569]">
                      English and Sinhala UI switching is prepared from the start.
                    </p>
                  </div>
                </div>

                <div className="mt-8 rounded-3xl border border-[#e6ecfb] bg-[#fbfcff] p-6">
                  <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#94a3b8]">
                    Why SME-GPT
                  </p>
                  <ul className="mt-4 space-y-3 text-[#475569]">
                    <li>• Upload invoices, purchase orders, and delivery notes</li>
                    <li>• Compare values and detect discrepancies instantly</li>
                    <li>• Support bilingual workflows with explainable outputs</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MobileShell>
  );
}