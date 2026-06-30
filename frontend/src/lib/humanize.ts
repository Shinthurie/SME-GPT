// Turns the query engine's internal/technical tokens (metric keys, flow types,
// operation strings like "aggregate_sum" / "sum(payable_amount)") into plain
// language an SME owner understands. Bilingual EN/SI. Used by the answer page
// and the derivation trace so the explainability UI stays jargon-free.

import { AppLanguage } from "@/lib/i18n";

type Bi = { en: string; si: string };

// Internal/technical metric keys that should never be shown to an end user.
const HIDDEN_METRIC_KEYS = new Set([
  "user_id", "tenant_id", "question_type", "operation", "engine", "task",
  "measure", "group_by", "plan", "rows_used", "scope", "retries",
  "fallback_used", "raw_question", "value_type", "row_ids",
]);

export function isHiddenMetric(key: string): boolean {
  return HIDDEN_METRIC_KEYS.has(key);
}

const METRIC_LABELS: Record<string, Bi> = {
  po_count: { en: "Purchase orders", si: "මිලදී ගැනීමේ ඇණවුම්" },
  dn_count: { en: "Delivery notes", si: "බෙදාහැරීමේ සටහන්" },
  invoice_count: { en: "Invoices", si: "ඉන්වොයිස්" },
  receipt_count: { en: "Receipts", si: "රිසිට්පත්" },
  supplier_count: { en: "Suppliers", si: "සැපයුම්කරුවන්" },
  customer_count: { en: "Customers", si: "පාරිභෝගිකයන්" },
  linked_count: { en: "Linked documents", si: "සම්බන්ධිත ලේඛන" },
  total_amount: { en: "Total amount", si: "මුළු මුදල" },
  amount: { en: "Amount", si: "මුදල" },
  count: { en: "Count", si: "ගණන" },
  period: { en: "Period", si: "කාල සීමාව" },
  status_filter: { en: "Status", si: "තත්ත්වය" },
  doc_type: { en: "Document type", si: "ලේඛන වර්ගය" },
  document_type: { en: "Document type", si: "ලේඛන වර්ගය" },
  document_id: { en: "Document", si: "ලේඛනය" },
  currency: { en: "Currency", si: "මුදල් ඒකකය" },
  row_count: { en: "Documents used", si: "භාවිත ලේඛන" },
};

function prettify(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bPo\b/g, "PO")
    .replace(/\bDn\b/g, "DN")
    .replace(/\bId\b/g, "ID");
}

export function metricLabel(key: string, lang: AppLanguage): string {
  const m = METRIC_LABELS[key];
  return m ? m[lang] : prettify(key);
}

const FLOW: Record<string, Bi> = {
  payable:      { en: "Payable",      si: "ගෙවිය යුතු"  },
  receivable:   { en: "Receivable",   si: "ලැබිය යුතු"  },
  cash_inflow:  { en: "Cash Inflow",  si: "මුදල් ලැබීම"  },
  cash_outflow: { en: "Cash Outflow", si: "මුදල් ගෙවීම"  },
  expense:      { en: "Expense",      si: "වියදම"        },
  income:       { en: "Income",       si: "ආදායම"        },
};

export function humanizeFlow(value: string | undefined | null, lang: AppLanguage): string {
  const v = FLOW[String(value || "").toLowerCase()];
  return v ? v[lang] : prettify(String(value || ""));
}

const STATUS: Record<string, Bi> = {
  overdue: { en: "Overdue", si: "කල් ඉකුත්" },
  paid: { en: "Paid", si: "ගෙවා ඇත" },
  not_paid: { en: "Unpaid", si: "නොගෙවූ" },
  unpaid: { en: "Unpaid", si: "නොගෙවූ" },
  pending: { en: "Pending", si: "පොරොත්තුවෙන්" },
  received: { en: "Received", si: "ලැබුණා" },
  not_received: { en: "Not received", si: "නොලැබුණු" },
  approved: { en: "Approved", si: "අනුමතයි" },
  rejected: { en: "Rejected", si: "ප්‍රතික්ෂේපයි" },
  fulfilled: { en: "Fulfilled", si: "ඉටු කළා" },
  cancelled: { en: "Cancelled", si: "අවලංගුයි" },
};

const DOCTYPE: Record<string, Bi> = {
  invoice: { en: "Invoice", si: "ඉන්වොයිස්" },
  receipt: { en: "Receipt", si: "රිසිට්පත" },
  po: { en: "Purchase order", si: "මිලදී ගැනීමේ ඇණවුම" },
  dn: { en: "Delivery note", si: "බෙදාහැරීමේ සටහන" },
};

export function humanizeDocType(value: string | undefined | null, lang: AppLanguage): string {
  const v = DOCTYPE[String(value || "").toLowerCase()];
  return v ? v[lang] : prettify(String(value || ""));
}

// Friendly text for a single metric value, given its key for context.
export function metricValue(key: string, value: unknown, lang: AppLanguage): string {
  if (value === null || value === undefined || value === "" || value === "NULL") return "—";
  const s = String(value);
  if (key === "status_filter") return STATUS[s.toLowerCase()]?.[lang] ?? prettify(s);
  if (key === "doc_type" || key === "document_type") return humanizeDocType(s, lang);
  if (key === "flow_type") return humanizeFlow(s, lang);
  if (Array.isArray(value)) return value.map(String).join(", ");
  return s;
}
