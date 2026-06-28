// IT-23 — pull overdue payables/receivables from the backend and surface them
// as notifications. Deduped so the same document isn't re-notified on every
// dashboard load (we remember which document IDs we've already alerted on).

import { addNotification } from "@/lib/notifications";
import { getStoredLanguage, ui } from "@/lib/i18n";

const BACKEND_URL = "http://127.0.0.1:8000";
const NOTIFIED_KEY = "sme_overdue_notified";

export type OverdueAlert = {
  document_id: string;
  document_type: string;
  kind: "payable" | "receivable";
  counterparty: string;
  amount: number | null;
  currency: string;
  due_date: string | null;
  doc_date: string | null;
  days_overdue: number | null;
};

function getNotifiedIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(NOTIFIED_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
}

function saveNotifiedIds(ids: Set<string>) {
  if (typeof window === "undefined") return;
  // Cap so the marker list can't grow unbounded.
  localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...ids].slice(-500)));
}

function buildMessage(alert: OverdueAlert): string {
  const t = ui[getStoredLanguage()];
  const parts: string[] = [];
  if (alert.counterparty) parts.push(alert.counterparty);
  if (alert.amount != null) parts.push(`${alert.currency} ${alert.amount}`);
  if (alert.days_overdue != null) parts.push(`${alert.days_overdue} ${t.overdueDaysSuffix}`);
  return `${alert.document_id} · ${parts.join(" · ")}`;
}

/**
 * Fetch overdue documents and add a notification for any not already alerted.
 * Best-effort: never throws (a backend/network failure simply produces no
 * alerts). Safe to call on every dashboard mount.
 */
export async function syncOverdueAlerts(token: string): Promise<void> {
  if (!token || typeof window === "undefined") return;

  let alerts: OverdueAlert[] = [];
  try {
    const res = await fetch(`${BACKEND_URL}/overdue-alerts`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return;
    const data = await res.json();
    if (!data?.success || !Array.isArray(data.alerts)) return;
    alerts = data.alerts as OverdueAlert[];
  } catch {
    return;
  }

  const t = ui[getStoredLanguage()];
  const notified = getNotifiedIds();
  let changed = false;

  for (const alert of alerts) {
    if (!alert.document_id || notified.has(alert.document_id)) continue;
    addNotification({
      type: "warning",
      title: alert.kind === "receivable" ? t.overdueReceivableTitle : t.overduePayableTitle,
      message: buildMessage(alert),
    });
    notified.add(alert.document_id);
    changed = true;
  }

  if (changed) saveNotifiedIds(notified);
}
