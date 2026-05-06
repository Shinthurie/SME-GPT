export type AppNotification = {
  id: string;
  title: string;
  message: string;
  type: "success" | "warning" | "error" | "info";
  createdAt: string;
  read: boolean;
};

const STORAGE_KEY = "sme_notifications";

function notifyChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event("notifications-updated"));
}

export function getNotifications(): AppNotification[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) return [];

    return parsed.map((item) => ({
      id: item.id || `${Date.now()}_${Math.random()}`,
      title: item.title || "Notification",
      message: item.message || "",
      type: item.type || "info",
      createdAt: item.createdAt || new Date().toISOString(),
      read: item.read === true,
    }));
  } catch {
    return [];
  }
}

export function saveNotifications(notifications: AppNotification[]) {
  if (typeof window === "undefined") return;

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(notifications.slice(0, 50))
  );

  notifyChange();
}

export function addNotification(
  notification: Omit<AppNotification, "id" | "createdAt" | "read">
) {
  if (typeof window === "undefined") return;

  const existing = getNotifications();

  const next: AppNotification = {
    ...notification,
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}_${Math.random()}`,
    createdAt: new Date().toISOString(),
    read: false,
  };

  saveNotifications([next, ...existing]);
}

export function markAllNotificationsRead() {
  const updated = getNotifications().map((item) => ({
    ...item,
    read: true,
  }));

  saveNotifications(updated);
}

export function clearNotifications() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  notifyChange();
}

export function hasUnreadNotifications() {
  return getNotifications().some((item) => item.read === false);
}