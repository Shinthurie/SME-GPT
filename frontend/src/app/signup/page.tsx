"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession, signupUser } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

export default function SignupPage() {
  const router = useRouter();

  const [lang, setLang] = useState<AppLanguage>("en");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

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

  const handleSignup = async (e: FormEvent) => {
    e.preventDefault();

  const ok = await signupUser({
  fullName,
  companyName,
  email,
  password,
});

    setMessage(t.signupSuccess);

    setTimeout(() => {
      router.push("/login");
    }, 1000);
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
                  {t.signUp}
                </h1>

                <p className="mt-2 text-center text-[11px] font-bold uppercase tracking-[0.18em] text-[#8a96ab]">
                  {t.enterpriseSubtitle}
                </p>

                <form onSubmit={handleSignup} className="mt-9 space-y-4">
                  <div>
                    <label className="mb-2 block text-[10px] font-bold uppercase tracking-[0.12em] text-[#7e8aa2]">
                      {t.fullName}
                    </label>
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[18px] text-[#93a0b5]">
                        person
                      </span>
                      <input
                        type="text"
                        placeholder={t.fullName}
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white pl-12 pr-4 text-[15px] text-slate-900 shadow-[0_4px_14px_rgba(15,23,42,0.04)] outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-[10px] font-bold uppercase tracking-[0.12em] text-[#7e8aa2]">
                      {t.companyName}
                    </label>
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[18px] text-[#93a0b5]">
                        domain
                      </span>
                      <input
                        type="text"
                        placeholder={t.companyName}
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white pl-12 pr-4 text-[15px] text-slate-900 shadow-[0_4px_14px_rgba(15,23,42,0.04)] outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                        required
                      />
                    </div>
                  </div>

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
                        placeholder={t.password}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="h-12 w-full rounded-2xl border border-[#e3e7f2] bg-white pl-12 pr-4 text-[15px] text-slate-900 shadow-[0_4px_14px_rgba(15,23,42,0.04)] outline-none transition focus:border-[#4d7cff] focus:ring-2 focus:ring-[#4d7cff]/15"
                        required
                      />
                    </div>
                  </div>

                  {message && (
                    <p className="text-[12px] font-medium text-emerald-600">
                      {message}
                    </p>
                  )}

                  <button
                    type="submit"
                    className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#07122f] text-[16px] font-bold text-white shadow-[0_10px_25px_rgba(7,18,47,0.22)] transition hover:translate-y-[1px] hover:opacity-95"
                  >
                    <span>{t.signUp}</span>
                    <span className="material-symbols-outlined text-[18px]">
                      person_add
                    </span>
                  </button>
                </form>

                <div className="mt-6 text-center">
                  <p className="text-[12px] text-[#7e8aa2]">
                    {t.haveAccount}{" "}
                    <a href="/login" className="font-bold text-[#4d7cff]">
                      {t.signIn}
                    </a>
                  </p>
                </div>
              </div>
            </div>

            <div className="hidden h-full lg:flex lg:items-center">
              <div className="w-full rounded-[30px] border border-[#d9dff0] bg-white p-8 xl:p-10 shadow-sm">
                <h2 className="text-4xl font-extrabold tracking-tight text-[#0f172a]">
                  Secure Workspace Setup
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[#64748b]">
                  Create a workspace for invoice analysis, OCR extraction, bilingual querying, and explainable AI review.
                </p>

                <div className="mt-10 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-3xl bg-[#eef4ff] p-6">
                    <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#2563ff]">
                      Structured Storage
                    </p>
                    <p className="mt-3 text-[#475569]">
                      Keep documents, extracted fields, and validation flows organized.
                    </p>
                  </div>

                  <div className="rounded-3xl bg-[#f8fafc] p-6">
                    <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#2563ff]">
                      Dual Language
                    </p>
                    <p className="mt-3 text-[#475569]">
                      UI terms can switch between English and Sinhala later without rewriting each page.
                    </p>
                  </div>
                </div>

                <div className="mt-8 rounded-3xl border border-[#e6ecfb] bg-[#fbfcff] p-6">
                  <p className="text-sm font-bold uppercase tracking-[0.12em] text-[#94a3b8]">
                    Secure by Design
                  </p>
                  <ul className="mt-4 space-y-3 text-[#475569]">
                    <li>• Create and manage your enterprise document workspace</li>
                    <li>• Prepare for OCR, semantic extraction, and validation</li>
                    <li>• Scale to bilingual workflows with clean UI foundations</li>
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