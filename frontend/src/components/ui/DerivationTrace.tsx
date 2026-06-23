"use client";

/**
 * Iteration 7 — Explainability UI.
 * Shows a step-by-step derivation trace for a query answer:
 *   Scope resolution → Document match → Computation → Answer generation
 */

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
}: DerivationTraceProps) {
  const docCount = evidence.length;
  const totalUsed = evidence.reduce(
    (sum, e) => sum + Number(e.amount_used ?? e.final_total_amount ?? 0),
    0
  );
  const currencies = [...new Set(evidence.map((e) => e.currency || "LKR"))];

  // Derive arithmetic operation from questionType
  const opLabel: Record<string, string> = {
    payable: "Sum of outstanding payable amounts",
    receivable: "Sum of outstanding receivable amounts",
    expense: "Sum of expense amounts",
    income: "Sum of income amounts",
    summary: "Aggregate across matched documents",
    invoice_list: "List matching invoices",
    receipt_list: "List matching receipts",
    po_list: "List matching purchase orders",
    dn_list: "List matching delivery notes",
  };

  return (
    <div className="rounded-[18px] border border-[#e2e8f0] bg-[#f8fafc] px-5 py-5">
      <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.12em] text-[#64748b]">
        Derivation Trace — How This Answer Was Computed
      </p>

      <div className="space-y-5">
        {/* Step 1 — Scope resolution */}
        <div>
          <StepBadge step={1} label="Scope Resolution" />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            Tenant-scoped query for company{" "}
            <span className="font-semibold text-[#0f172a]">"{companyName}"</span>.{" "}
            Found <span className="font-semibold">{docCount}</span> matching document
            {docCount !== 1 ? "s" : ""}.
          </div>
        </div>

        {/* Step 2 — Document matches */}
        <div>
          <StepBadge step={2} label="Document Match" />
          <div className="ml-10 mt-2 space-y-2">
            {evidence.length === 0 ? (
              <div className="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-700">
                No documents matched the scope. Check the company name or add documents.
              </div>
            ) : (
              evidence.map((e, i) => (
                <div
                  key={`${e.document_id}-${i}`}
                  className="flex items-center justify-between rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px]"
                >
                  <div>
                    <span className="font-semibold text-[#0f172a]">{e.document_id}</span>
                    <span className="ml-2 text-[#64748b]">{e.document_type} · {e.flow_type}</span>
                  </div>
                  <span className="font-semibold text-[#2563ff]">
                    {e.currency || "LKR"} {formatAmount(e.amount_used ?? e.final_total_amount)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Step 3 — Computation */}
        <div>
          <StepBadge step={3} label="Computation" />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            <p>
              <span className="font-semibold">Operation:</span>{" "}
              {opLabel[questionType] || "Aggregate"}
            </p>
            {docCount > 0 && (
              <p className="mt-1">
                <span className="font-semibold">Formula:</span>{" "}
                {currencies.map((c) => {
                  const cSum = evidence
                    .filter((e) => (e.currency || "LKR") === c)
                    .reduce((s, e) => s + Number(e.amount_used ?? e.final_total_amount ?? 0), 0);
                  return (
                    <span key={c} className="mr-3 font-mono text-[#0f172a]">
                      {c} {formatAmount(cSum)}
                    </span>
                  );
                })}
              </p>
            )}
            {Object.keys(metrics).length > 0 && (
              <div className="mt-3 border-t border-[#e2e8f0] pt-3">
                <p className="font-semibold">Query metrics:</p>
                <ul className="mt-1 space-y-0.5">
                  {Object.entries(metrics)
                    .filter(([k]) => !["user_id"].includes(k))
                    .map(([k, v]) => (
                      <li key={k} className="text-[12px]">
                        <span className="text-[#64748b]">{k}:</span>{" "}
                        <span className="font-medium text-[#0f172a]">{String(v)}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Step 4 — Answer generation */}
        <div>
          <StepBadge step={4} label="Answer Generation" />
          <div className="ml-10 mt-2 rounded-[12px] border border-[#e2e8f0] bg-white px-4 py-3 text-[13px] text-[#334155]">
            {docCount > 0 ? (
              <p>
                Answer grounded in {docCount} document{docCount !== 1 ? "s" : ""}.
                Total: <span className="font-mono font-semibold text-[#0f172a]">
                  {currencies.map((c) => `${c} ${formatAmount(
                    evidence.filter(e => (e.currency || "LKR") === c)
                      .reduce((s, e) => s + Number(e.amount_used ?? e.final_total_amount ?? 0), 0)
                  )}`).join(" + ")}
                </span>
              </p>
            ) : (
              <p className="text-amber-700">
                No documents contributed to this answer. The answer reflects an empty result set.
              </p>
            )}
            <p className="mt-2 text-[12px] text-[#64748b]">
              Source: tenant-isolated Postgres (FinancialDocument + LineItem tables)
            </p>
          </div>
        </div>
      </div>

      {/* Low-confidence warning */}
      {docCount === 0 && (
        <div className="mt-4 flex items-start gap-2 rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-700">
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span>
            <strong>Low confidence:</strong> No documents matched this query. The answer
            may be a fallback estimate. Verify the company name or add documents.
          </span>
        </div>
      )}
    </div>
  );
}
