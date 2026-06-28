// Shared display formatters for documents shown to SME owners.
// Keeps money + naming consistent across dashboard, repository and answer pages.

const NULLISH = new Set(["", "null", "nan", "undefined", "n/a", "none"]);

function isBlank(v: unknown): boolean {
  if (v == null) return true;
  return NULLISH.has(String(v).trim().toLowerCase());
}

/**
 * Format a money amount as "LKR 1,500.00" with thousands separators.
 * Strips any currency symbols/commas the OCR may have left in the value.
 * Returns "" when the amount is blank/NULL so callers can show a neutral dash.
 */
export function formatMoney(
  amount: string | number | null | undefined,
  currency?: string | null,
): string {
  if (isBlank(amount)) return "";
  const cur = isBlank(currency) ? "LKR" : String(currency).trim();
  const num = Number(String(amount).replace(/[^0-9.-]/g, ""));
  if (!Number.isFinite(num)) return `${cur} ${amount}`;
  return `${cur} ${num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * The OTHER party on a document. On save the backend forces `company_name` to
 * the user's own company and stores the counterparty in `supplier_name`, so the
 * other party is always `supplier_name`. Returns "" when none was extracted.
 */
export function otherPartyName(doc: { supplier_name?: string | null }): string {
  return isBlank(doc.supplier_name) ? "" : String(doc.supplier_name).trim();
}
