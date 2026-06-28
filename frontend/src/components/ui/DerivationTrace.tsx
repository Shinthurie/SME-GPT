"use client";

/**
 * Explainability UI — shows, in plain language, how an answer was worked out:
 *   Where we looked → Documents we used → How we calculated → Your answer
 *
 * Deliberately free of technical jargon (no table names, no "aggregate_sum",
 * no "tenant-scoped result set") so an SME owner can follow the reasoning.
 */

import { AppLanguage } from "@/lib/i18n";
import { isHiddenMetric, metricLabel, metricValue, humanizeFlow, humanizeDocType } from "@/lib/humanize";

type EvidenceItem = {
  document_id: string;
  document_type: string;
  company_name: string;
  supplier_name: string;
  flow_type: string;
  currency?: string;
  final_total_amount: number;
  payable_amount: number;
  amount_used?: number;
  reason_used: string;
};

type DerivationTraceProps = {
  evidence: EvidenceItem[];
  metrics: Record<string, unknown>;
  questionType: string;
  companyName: string;
  lang?: AppLanguage;
};

function formatAmount(v: number | undefined | null): string {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function StepBadge({ step, label }: { step: number; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#2563ff] text-[11px] font-bold text-white">
        {step}
      </div>
      <span className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#475569]">
        {label}
      </span>
    </div>
  );
}

export default function DerivationTrace({
  evidence,
  metrics,
  questionType,
  companyName,
  lang = "en",
}: DerivationTraceProps) {
  const L = (en: string, si: string) => (lang === "si" ? si : en);
  const docCount = evidence.length;
  const currencies = [...new Set(evidence.map((e) => e.currency || "LKR"))];

  // Plain-language description of the calculation, by question type.
  const opLabel: Record<string, string> = {
    payable: L("Added up the money you still owe", "ඔබ තවම ගෙවිය යුතු මුදල් එකතු කළා"),
    receivable: L("Added up the money owed to you", "ඔබට ලැබිය යුතු මුදල් එකතු කළා"),
    expense: L("Added up your expenses", "ඔබගේ වියදම් එකතු කළා"),
    income: L("Added up your income", "ඔබගේ ආදායම එකතු කළා"),
    summary: L("Combined the matching documents", "ගැළපෙන ලේඛන එකතු කළා"),
    invoice_list: L("Listed the matching invoices", "ගැළපෙන ඉන්වොයිස් ලැයිස්තුගත කළා"),
    receipt_list: L("Listed the matching receipts", "ගැළපෙන රිසිට්පත් ලැයිස්තුගත කළා"),
    po_list: L("Listed the matching purchase orders", "ගැළපෙන ඇණවුම් ලැයිස්තුගත කළා"),
    dn_list: L("Listed the matching delivery notes", "ගැළපෙන බෙදාහැරීමේ සටහන් ලැයිස්තුගත කළා"),
  };

  const visibleMetrics = Object.entries(metrics).filter(([k]) => !isHiddenMetric(k));

  return (
    <div className="rounded-[18px] border border-[#e2e8f0] bg-[#f8fafc] px-5 py-5">
      <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
        {L("How this answer was worked out", "මෙම පිළිතුර ලැබුණු ආකාරය")}
      </p>

      <div className="space-y-5">
        {/* Step 1 — Where we looked */}
        <div>
          <StepBadge step={1} label={L("Where we looked", "අප සෙව්වේ කොහෙද")} />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            {L("We searched only your own saved documents for", "ඔබගේ සුරැකි ලේඛන තුළ පමණක් සෙව්වා —")}{" "}
            <span className="font-semibold text-[#0f172a]">&quot;{companyName}&quot;</span>.{" "}
            {L("Found", "හමු විය")} <span className="font-semibold">{docCount}</span>{" "}
            {docCount === 1 ? L("matching document.", "ගැළපෙන ලේඛනයක්.") : L("matching documents.", "ගැළපෙන ලේඛන.")}
          </div>
        </div>

        {/* Step 2 — Documents we used */}
        <div>
          <StepBadge step={2} label={L("Documents we used", "අප භාවිත කළ ලේඛන")} />
          <div className="ml-10 mt-2 space-y-2">
            {evidence.length === 0 ? (
              <div className="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-700">
                {L("No documents matched. Check the company name or add documents.",
                   "ලේඛන කිසිවක් නොගැළපුණි. සමාගම් නම පරීක්ෂා කරන්න හෝ ලේඛන එක් කරන්න.")}
              </div>
            ) : (
              evidence.map((e, i) => (
                <div
                  key={`${e.document_id}-${i}`}
                  className="flex items-center justify-between rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px]"
                >
                  <div>
                    <span className="font-semibold text-[#0f172a]">{e.document_id}</span>
                    <span className="ml-2 text-[#64748b]">
                      {humanizeDocType(e.document_type, lang)} · {humanizeFlow(e.flow_type, lang)}
                    </span>
                  </div>
                  <span className="font-semibold text-[#2563ff]">
                    {e.currency || "LKR"} {formatAmount(e.amount_used ?? e.final_total_amount)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Step 3 — How we calculated */}
        <div>
          <StepBadge step={3} label={L("How we calculated", "අප ගණනය කළ ආකාරය")} />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            <p>
              <span className="font-semibold">{L("What we did:", "අප කළේ:")}</span>{" "}
              {opLabel[questionType] || L("Combined the matching documents", "ගැළපෙන ලේඛන එකතු කළා")}
            </p>
            {docCount > 0 && (
              <p className="mt-1">
                <span className="font-semibold">{L("Total:", "එකතුව:")}</span>{" "}
                {currencies.map((c) => {
                  const cSum = evidence
                    .filter((e) => (e.currency || "LKR") === c)
                    .reduce((s, e) => s + Number(e.amount_used ?? e.final_total_amount ?? 0), 0);
                  return (
                    <span key={c} className="mr-3 font-semibold text-[#0f172a]">
                      {c} {formatAmount(cSum)}
                    </span>
                  );
                })}
              </p>
            )}
            {visibleMetrics.length > 0 && (
              <div className="mt-3 border-t border-[#e2e8f0] pt-3">
                <p className="font-semibold">{L("Details:", "විස්තර:")}</p>
                <ul className="mt-1 space-y-0.5">
                  {visibleMetrics.map(([k, v]) => (
                    <li key={k} className="text-[12px]">
                      <span className="text-[#64748b]">{metricLabel(k, lang)}:</span>{" "}
                      <span className="font-medium text-[#0f172a]">{metricValue(k, v, lang)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Step 4 — Your answer */}
        <div>
          <StepBadge step={4} label={L("Your answer", "ඔබගේ පිළිතුර")} />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            {docCount > 0 ? (
              <p>
                {L("Based on", "පදනම් වී ඇත්තේ")} {docCount}{" "}
                {docCount === 1 ? L("of your documents.", "ඔබගේ ලේඛනයක් මත.") : L("of your documents.", "ඔබගේ ලේඛන මත.")}{" "}
                {L("Total:", "එකතුව:")}{" "}
                <span className="font-semibold text-[#0f172a]">
                  {currencies.map((c) => `${c} ${formatAmount(
                    evidence.filter(e => (e.currency || "LKR") === c)
                      .reduce((s, e) => s + Number(e.amount_used ?? e.final_total_amount ?? 0), 0)
                  )}`).join(" + ")}
                </span>
              </p>
            ) : (
              <p className="text-amber-700">
                {L("No documents matched, so there is nothing to total.",
                   "ලේඛන කිසිවක් නොගැළපුණි, එබැවින් එකතු කිරීමට කිසිවක් නැත.")}
              </p>
            )}
            <p className="mt-2 text-[12px] text-[#64748b]">
              {L("Based only on your own saved documents — every figure is traceable to a document above.",
                 "ඔබගේ සුරැකි ලේඛන මත පමණක් පදනම්ව — සෑම අගයක්ම ඉහත ලේඛනයකට සම්බන්ධ කළ හැක.")}
            </p>
          </div>
        </div>
      </div>

      {/* Low-confidence warning */}
      {docCount === 0 && (
        <div className="mt-4 flex items-start gap-2 rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-700">
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span>
            <strong>{L("Please check:", "කරුණාකර පරීක්ෂා කරන්න:")}</strong>{" "}
            {L("No documents matched this question. Verify the company name or add documents.",
               "මෙම ප්‍රශ්නයට ලේඛන කිසිවක් නොගැළපුණි. සමාගම් නම තහවුරු කරන්න හෝ ලේඛන එක් කරන්න.")}
          </span>
        </div>
      )}
    </div>
  );
}
