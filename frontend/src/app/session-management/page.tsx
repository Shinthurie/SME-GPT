"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession } from "@/lib/auth";

type TrustedDevice = {
  id: string;
  deviceToken: string;
  deviceName: string | null;
  ipAddress: string | null;
  userAgent: string | null;
  trustedAt: string;
  lastUsedAt: string;
};

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function SessionManagementPage() {
  const router = useRouter();

  const [devices, setDevices] = useState<TrustedDevice[]>([]);
  const [currentDeviceToken, setCurrentDeviceToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState("");

  const loadSessions = async () => {
    try {
      setLoading(true);
      setMessage("");

      const session = await getSession();
      if (!session) {
        router.push("/login");
        return;
      }

      const res = await fetch("/api/sessions");
      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to load sessions");
        return;
      }

      setDevices(data.devices || []);
      setCurrentDeviceToken(data.currentDeviceToken || null);
    } catch (error) {
      console.error("LOAD SESSIONS ERROR:", error);
      setMessage("Something went wrong while loading sessions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleRemoveDevice = async (deviceId: string) => {
    try {
      setActionLoading(true);
      setMessage("");

      const res = await fetch("/api/sessions", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ deviceId }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to remove device");
        return;
      }

      setMessage("Trusted device removed");
      await loadSessions();
    } catch (error) {
      console.error("REMOVE DEVICE ERROR:", error);
      setMessage("Something went wrong");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveOthers = async () => {
    try {
      setActionLoading(true);
      setMessage("");

      const res = await fetch("/api/sessions", {
        method: "POST",
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to remove other devices");
        return;
      }

      setMessage(data.message || "All other trusted devices removed");
      await loadSessions();
    } catch (error) {
      console.error("REMOVE OTHERS ERROR:", error);
      setMessage("Something went wrong");
    } finally {
      setActionLoading(false);
    }
  };

  const handleTrustCurrentDevice = async () => {
    try {
      setActionLoading(true);
      setMessage("");

      const res = await fetch("/api/sessions/trust-current", {
        method: "POST",
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to trust device");
        return;
      }

      setMessage(data.message || "Device trusted successfully");
      await loadSessions();
    } catch (error) {
      console.error("TRUST CURRENT DEVICE ERROR:", error);
      setMessage("Something went wrong");
    } finally {
      setActionLoading(false);
    }
  };

  const currentTrustedDevice = devices.find(
    (device) => device.deviceToken === currentDeviceToken
  );

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
                Session Management
              </h1>
              <p className="mt-1 text-[13px] text-[#64748b]">
                Manage trusted devices for your SME-GPT account
              </p>
            </div>
            <LanguageSwitcher />
          </div>

          <div className="mb-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => router.push("/profile")}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-bold text-[#64748b]"
            >
              Back to Profile
            </button>

            <button
              type="button"
              onClick={() => {
                if (!confirm("This will remove all other trusted devices. Continue?")) return;
                handleRemoveOthers();
              }}
              disabled={actionLoading}
              className="rounded-xl bg-[#07122f] px-4 py-2 text-[13px] font-bold text-white"
            >
              {actionLoading ? "Working..." : "Logout All Other Devices"}
            </button>
          </div>

          {message && (
            <p className="mb-4 text-[13px] text-[#2563ff]">{message}</p>
          )}

          <div className="rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-[16px] font-bold text-[#0f172a]">
              Current Device Status
            </h2>

            <div className="mt-4 rounded-[16px] border border-slate-200 bg-[#fafbff] p-4">
              <p className="text-[15px] font-bold text-[#0f172a]">This Device</p>

              {currentTrustedDevice ? (
                <>
                  <p className="mt-1 text-[13px] font-semibold text-[#16a34a]">
                    Trusted Device
                  </p>
                  <p className="mt-2 text-[12px] text-[#64748b]">
                    Last used: {formatDate(currentTrustedDevice.lastUsedAt)}
                  </p>
                  <p className="mt-1 text-[12px] text-[#64748b] break-words">
                    {currentTrustedDevice.deviceName || "Unknown Device"}
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-1 text-[13px] font-semibold text-red-500">
                    Not Trusted
                  </p>

                  <button
                    onClick={handleTrustCurrentDevice}
                    disabled={actionLoading}
                    className="mt-3 rounded-xl bg-[#2563ff] px-4 py-2 text-[12px] font-bold text-white"
                  >
                    {actionLoading ? "Working..." : "Trust This Device"}
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="mt-6 rounded-[20px] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="text-[16px] font-bold text-[#0f172a]">
                Trusted Devices
              </h2>
              <p className="mt-1 text-[13px] text-[#64748b]">
                Removing a device means future logins on that device will require email verification again.
              </p>
            </div>

            {loading ? (
              <div className="px-5 py-6 text-[14px] text-[#64748b]">
                Loading trusted devices...
              </div>
            ) : devices.length === 0 ? (
              <div className="px-5 py-6 text-[14px] text-[#64748b]">
                No trusted devices found.
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {devices.map((device) => {
                  const isCurrent = device.deviceToken === currentDeviceToken;

                  return (
                    <div
                      key={device.id}
                      className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-[15px] font-bold text-[#0f172a]">
                            {device.deviceName || "Unknown Device"}
                          </p>

                          {isCurrent && (
                            <span className="rounded-full bg-[#e0edff] px-2.5 py-1 text-[10px] font-bold text-[#2563ff]">
                              This Device
                            </span>
                          )}
                        </div>

                        <p className="mt-1 break-all text-[13px] text-[#64748b]">
                          {device.ipAddress || "Unknown IP"}
                        </p>

                        <p className="mt-1 break-words text-[12px] text-[#94a3b8]">
                          {device.userAgent || "Unknown browser"}
                        </p>

                        <div className="mt-2 text-[12px] text-[#64748b]">
                          <p>Trusted: {formatDate(device.trustedAt)}</p>
                          <p>Last used: {formatDate(device.lastUsedAt)}</p>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={actionLoading}
                          onClick={() => {
                            if (!confirm("Remove this trusted device?")) return;
                            handleRemoveDevice(device.id);
                          }}
                          className="rounded-xl border border-red-300 bg-[#fff5f5] px-4 py-2 text-[12px] font-bold text-red-600"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-6 rounded-[20px] border border-amber-200 bg-[#fffaf0] p-5">
            <h3 className="text-[15px] font-bold text-[#0f172a]">
              Important Note
            </h3>
            <p className="mt-2 text-[13px] leading-6 text-[#64748b]">
              Removing a trusted device does not immediately destroy an already active login session on that device.
              It prevents that device from skipping email verification on future logins.
            </p>
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}