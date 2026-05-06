"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import {
  getNotifications,
  clearNotifications,
  markAllNotificationsRead,
  AppNotification,
} from "@/lib/notifications";

function formatTime(value: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function getTypeStyles(type: AppNotification["type"]) {
  switch (type) {
    case "success":
      return {
        card: "bg-green-50 border-green-200 text-green-700",
        icon: "check_circle",
      };
    case "warning":
      return {
        card: "bg-amber-50 border-amber-200 text-amber-700",
        icon: "warning",
      };
    case "error":
      return {
        card: "bg-red-50 border-red-200 text-red-700",
        icon: "error",
      };
    default:
      return {
        card: "bg-blue-50 border-blue-200 text-blue-700",
        icon: "notifications",
      };
  }
}

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  useEffect(() => {
    const items = getNotifications();
    setNotifications(items);

    if (items.some((item) => item.read === false)) {
      markAllNotificationsRead();
    }
  }, []);

  const handleClearAll = () => {
    clearNotifications();
    setNotifications([]);
  };

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-5 flex items-center justify-between">
            <button
              onClick={() => router.back()}
              className="text-[14px] font-medium text-[#2563ff]"
            >
              ← Back
            </button>

            <div className="flex items-center gap-2">
              <LanguageSwitcher />

              <button
                onClick={handleClearAll}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[12px] font-semibold text-[#64748b]"
              >
                Clear All
              </button>
            </div>
          </div>

          <h1 className="text-[24px] font-extrabold text-[#0f172a]">
            Notifications
          </h1>

          <p className="mt-2 text-[14px] text-[#64748b]">
            Recent system updates and activity alerts.
          </p>

          <div className="mt-6 space-y-4">
            {notifications.length === 0 ? (
              <div className="rounded-[18px] border border-slate-200 bg-white p-5 text-[14px] text-[#64748b] shadow-sm">
                No notifications available.
              </div>
            ) : (
              notifications.map((item) => {
                const styles = getTypeStyles(item.type);

                return (
                  <div
                    key={item.id}
                    className={`rounded-[18px] border p-5 shadow-sm ${styles.card}`}
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/70">
                        <span className="material-symbols-outlined text-[20px]">
                          {styles.icon}
                        </span>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <h2 className="text-[15px] font-bold">
                              {item.title}
                            </h2>

                            {!item.read && (
                              <span className="rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white">
                                NEW
                              </span>
                            )}
                          </div>

                          <span className="text-[11px] opacity-70">
                            {formatTime(item.createdAt)}
                          </span>
                        </div>

                        <p className="mt-2 text-[13px] leading-6">
                          {item.message}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}