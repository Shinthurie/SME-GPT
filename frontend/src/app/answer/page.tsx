"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { AppLanguage, getStoredLanguage } from "@/lib/i18n";

type EvidenceItem = {
  document_id: string;
  document_type: string;
  date: string;
  company_name: string;
  supplier_name: string;
  order_id: string;
  flow_type: string;
  received_status: string;
  paid_status: string;
  final_total_amount: number;
  payable_amount: number;
  reason_used: string;
};

type QueryResult = {
  success: boolean;
  company_name: string;
  question: string;
  answer: string;
  explanation: string;
  evidence: EvidenceItem[];
  metrics: Record<string, any>;
  source_file: string;
};

export default function AnswerPage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [result, setResult] = useState<QueryResult | null>(null);

  useEffect(() => {
    setLang(getStoredLanguage());

    const raw = sessionStorage.getItem("query_result");
    if (!raw) return;

    try {
      setResult(JSON.parse(raw));
    } catch {
      setResult(null);
    }
  }, []);

  if (!result) {
    return (
      <MobileShell>
        <div className="min-h-screen bg-[#f6f7fb] pb-24">
          <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
            <button
              onClick={() => router.push("/query")}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>

            <div className="mt-8 rounded-[18px] border border-slate-200 bg-white p-6 text-center text-[14px] text-[#64748b] shadow-sm">
              No query result found.
            </div>
          </main>
          <BottomNav />
        </div>
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={() => router.push("/query")}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>
            <div className="flex items-center gap-2">
              <LanguageSwitcher />
            </div>
          </div>

          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
            Explainable Financial Answer
          </p>
          <h1 className="text-[24px] font-extrabold text-[#0f172a]">
            Query Result
          </h1>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Company Context
            </p>
            <p className="mt-3 text-[14px] font-semibold text-[#0f172a]">
              {result.company_name}
            </p>
          </div>

          <div className="mt-4 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Question
            </p>
            <p className="mt-3 text-[14px] leading-7 text-[#334155]">
              {result.question}
            </p>
          </div>

          <div className="mt-6 rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
                Final Answer
              </p>
              <span className="rounded-full bg-[#eef4ff] px-4 py-2 text-[12px] font-bold text-[#2563ff]">
                Explainable
              </span>
            </div>

            <p className="mt-4 text-[15px] leading-8 text-[#111827]">
              {result.answer}
            </p>
          </div>

          <div className="mt-6 rounded-[18px] border border-[#c8d7ff] bg-[#eef4ff] p-5">
            <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#2563ff]">
              Source
            </p>
            <p className="mt-2 text-[14px] text-[#334155]">
              Answer generated only from: <span className="font-semibold">{result.source_file}</span>
            </p>
            <p className="mt-2 text-[14px] text-[#334155]">
              {result.explanation}
            </p>
          </div>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Metrics
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {Object.entries(result.metrics || {}).map(([key, value]) => (
                <div
                  key={key}
                  className="rounded-[14px] border border-slate-200 px-4 py-3"
                >
                  <p className="text-[11px] text-[#94a3b8]">{key}</p>
                  <p className="mt-1 text-[15px] font-semibold text-[#0f172a]">
                    {String(value)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
              Evidence Documents
            </p>

            <div className="mt-4 space-y-4">
              {result.evidence && result.evidence.length > 0 ? (
                result.evidence.map((item, index) => (
                  <div
                    key={`${item.document_id}-${index}`}
                    className="rounded-[14px] border border-slate-200 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-[15px] font-bold text-[#0f172a]">
                        {item.document_id}
                      </p>
                      <span className="rounded-xl bg-[#eef4ff] px-3 py-1.5 text-[11px] font-semibold text-[#2563ff]">
                        {item.document_type}
                      </span>
                    </div>

                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Date:</span> {item.date}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Order ID:</span> {item.order_id}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Company:</span> {item.company_name}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Supplier:</span> {item.supplier_name}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Flow Type:</span> {item.flow_type}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Final Total:</span> {item.final_total_amount}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Payable Amount:</span> {item.payable_amount}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Received Status:</span> {item.received_status}
                      </p>
                      <p className="text-[13px] text-[#334155]">
                        <span className="font-semibold">Paid Status:</span> {item.paid_status}
                      </p>
                    </div>

                    <div className="mt-3 rounded-[12px] bg-[#f8fafc] p-3">
                      <p className="text-[12px] text-[#64748b]">
                        <span className="font-semibold">Why used:</span> {item.reason_used}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-[14px] text-[#64748b]">No evidence documents found.</p>
              )}
            </div>
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}