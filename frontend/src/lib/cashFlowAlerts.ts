// Pull cash-flow-health alerts (negative/declining net cash flow, backend/alerts.py)
// from the backend and surface them as notifications. Complementary to
// overdueAlerts.ts (per-document overdue payments) -- this is aggregate
// business-health signal, not tied to one document. Same dedup pattern:
// remember which alert ids we've already notified on.

import { addNotification } from "@/lib/notifications";
import { resolveBackendUrl } from "@/lib/backendUrl";

const BACKEND_URL = resolveBackendUrl();
const NOTIFIED_KEY = "sme_cash_flow_alert_notified";

export type CashFlowAlert = {
  id: string;
  created_at: string;
  rule_id: string;
  period: string;
  severity: "warning" | "info";
  title: string;
  message: string;
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
  localStorage.setItem(NOTIFIED_KEY, JSON.stringify([...ids].slice(-200)));
}

/**
 * Fetch cash-flow alerts and add a notification for any not already alerted.
 * Best-effort: never throws. Safe to call on every dashboard mount.
 */
export async function syncCashFlowAlerts(token: string): Promise<void> {
  if (!token || typeof window === "undefined") return;

  let alerts: CashFlowAlert[] = [];
  try {
    const res = await fetch(`${BACKEND_URL}/alerts`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return;
    const data = await res.json();
    if (!data?.success || !Array.isArray(data.alerts)) return;
    alerts = data.alerts as CashFlowAlert[];
  } catch {
    return;
  }

  const notified = getNotifiedIds();
  let changed = false;

  for (const alert of alerts) {
    if (!alert.id || notified.has(alert.id)) continue;
    addNotification({
      type: alert.severity === "warning" ? "warning" : "info",
      title: alert.title,
      message: alert.message,
    });
    notified.add(alert.id);
    changed = true;
  }

  if (changed) saveNotifiedIds(notified);
}
