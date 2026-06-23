"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession, logoutUser, SessionUser, getStoredToken } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui, setStoredLanguage } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

const BACKEND_URL = "http://127.0.0.1:8000";

type ProfileData = {
  fullName: string;
  profileImage: string;
  companyName: string;
  businessUnit: string;
  primaryLanguage: string;
  autoClassify: boolean;
  twoFactorEnabled: boolean;
  phone: string;
  jobTitle: string;
  country: string;
};

/* ── Shared sub-components ────────────────────────────────────────── */

function SectionHeader({ icon, title, danger }: { icon: string; title: string; danger?: boolean }) {
  return (
    <div className="mb-2 mt-7 flex items-center gap-2">
      <span
        className="material-symbols-outlined text-[16px]"
        style={{ color: danger ? "#dc2626" : "var(--text-3)" }}
      >
        {icon}
      </span>
      <p
        className="text-[11px] font-bold uppercase tracking-[0.12em]"
        style={{ color: danger ? "#dc2626" : "var(--text-3)" }}
      >
        {title}
      </p>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="overflow-hidden rounded-2xl shadow-sm"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      {children}
    </div>
  );
}

function Divider() {
  return <div style={{ borderTop: "1px solid var(--border)" }} />;
}

function Toggle({ enabled, onClick, disabled }: { enabled: boolean; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-7 w-12 rounded-full p-[3px] transition ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      style={{ background: enabled ? "var(--brand-mid)" : "var(--border)" }}
    >
      <div
        className="h-5 w-5 rounded-full bg-white shadow-sm transition-transform"
        style={{ transform: enabled ? "translateX(20px)" : "translateX(0)" }}
      />
    </button>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 px-5 py-3.5 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[12px] text-[var(--text-3)]">{label}</p>
      <p className="text-[14px] font-semibold text-[var(--text-1)]">{value || "—"}</p>
    </div>
  );
}

function InputRow({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div className="grid gap-1 px-5 py-3 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[12px] text-[var(--text-3)]">{label}</p>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || label}
        className="field-input h-10 w-full rounded-xl border px-3 text-[14px] transition"
      />
    </div>
  );
}

function SelectRow({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <div className="grid gap-1 px-5 py-3 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[12px] text-[var(--text-3)]">{label}</p>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="field-input h-10 w-full rounded-xl border px-3 text-[14px] transition"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function ActionRow({ icon, title, subtitle, iconBg, iconColor, right, onClick }: {
  icon: string; title: string; subtitle?: string;
  iconBg?: string; iconColor?: string;
  right?: React.ReactNode; onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-[var(--surface-2)]"
    >
      <div className="flex items-center gap-4">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ background: iconBg || "var(--brand-tint)", color: iconColor || "var(--brand-mid)" }}
        >
          <span className="material-symbols-outlined text-[18px]">{icon}</span>
        </div>
        <div>
          <p className="text-[14px] font-medium text-[var(--text-1)]">{title}</p>
          {subtitle && <p className="text-[12px] text-[var(--text-3)]">{subtitle}</p>}
        </div>
      </div>
      {right}
    </button>
  );
}

/* ── Page ─────────────────────────────────────────────────────────── */

export default function ProfilePage() {
  const router = useRouter();
  const { theme, toggle: toggleTheme } = useTheme();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [session, setSession] = useState<SessionUser | null>(null);
  const [form, setForm] = useState<ProfileData>({
    fullName: "", profileImage: "", companyName: "", businessUnit: "",
    primaryLanguage: "en", autoClassify: true, twoFactorEnabled: false,
    phone: "", jobTitle: "", country: "",
  });
  const [initialForm, setInitialForm] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [queryCount, setQueryCount] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLang(getStoredLanguage());
      const s = await getSession();
      if (!s) { router.push("/login"); return; }
      setSession(s);

      try {
        const res = await fetch("/api/profile", { cache: "no-store" });
        const data = await res.json();
        if (res.ok && data.user) {
          const d: ProfileData = {
            fullName: data.user.fullName || s.fullName || "",
            profileImage: data.user.profileImage || "",
            companyName: data.user.companyName || "",
            businessUnit: data.user.businessUnit || "",
            primaryLanguage: getStoredLanguage(),
            autoClassify: data.user.autoClassify ?? true,
            twoFactorEnabled: data.user.twoFactorEnabled ?? false,
            phone: data.user.phone || "",
            jobTitle: data.user.jobTitle || "",
            country: data.user.country || "",
          };
          setForm(d);
          setInitialForm(d);
        }
      } catch (err) {
        console.error("PROFILE LOAD ERROR:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [router]);

  useEffect(() => {
    const onLangChanged = (e: Event) => {
      const next = (e as CustomEvent<AppLanguage>).detail;
      if (next) { setLang(next); setForm((p) => (isEditing ? p : { ...p, primaryLanguage: next })); }
    };
    window.addEventListener("app-language-changed", onLangChanged as EventListener);
    return () => window.removeEventListener("app-language-changed", onLangChanged as EventListener);
  }, [isEditing]);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    fetch(`${BACKEND_URL}/query-history`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) => r.json())
      .then((d) => { if (d.success) setQueryCount((d.history || []).length); })
      .catch(() => {});
  }, []);

  const update = (key: keyof ProfileData, val: string | boolean) =>
    setForm((p) => ({ ...p, [key]: val }));

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fullName: form.fullName, profileImage: form.profileImage,
          companyName: form.companyName, businessUnit: form.businessUnit,
          primaryLanguage: form.primaryLanguage, autoClassify: form.autoClassify,
          phone: form.phone, jobTitle: form.jobTitle, country: form.country,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setMessage(data.error || "Failed to save"); return; }

      const updated: ProfileData = {
        fullName: data.user.fullName || form.fullName,
        profileImage: data.user.profileImage || form.profileImage,
        companyName: data.user.companyName || "",
        businessUnit: data.user.businessUnit || "",
        primaryLanguage: data.user.primaryLanguage || "en",
        autoClassify: data.user.autoClassify ?? true,
        twoFactorEnabled: form.twoFactorEnabled,
        phone: data.user.phone || "",
        jobTitle: data.user.jobTitle || "",
        country: data.user.country || "",
      };
      setForm(updated);
      setInitialForm(updated);
      setStoredLanguage(updated.primaryLanguage as AppLanguage);
      setLang(updated.primaryLanguage as AppLanguage);
      setMessage("Profile saved successfully");
      setIsEditing(false);
    } catch {
      setMessage("Something went wrong");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle2FA = async () => {
    const next = !form.twoFactorEnabled;
    try {
      const res = await fetch("/api/profile/two-factor", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      const data = await res.json();
      if (!res.ok) { setMessage(data.error || "Failed to update 2FA"); return; }
      update("twoFactorEnabled", data.twoFactorEnabled);
      setInitialForm((p) => p ? { ...p, twoFactorEnabled: data.twoFactorEnabled } : p);
      setMessage(data.twoFactorEnabled ? "Two-factor authentication enabled" : "Two-factor authentication disabled");
    } catch {
      setMessage("Failed to update 2FA");
    }
  };

  const handleLogout = async () => {
    try { await logoutUser(); } catch {}
    sessionStorage.removeItem("query_result");
    sessionStorage.removeItem("selected_query_history");
    router.push("/login");
  };

  const handleExportData = async () => {
    setExporting(true);
    setMessage("");
    try {
      const token = getStoredToken();
      const res = await fetch(`${BACKEND_URL}/user/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        setMessage(data.message || "Failed to export data");
        return;
      }
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sme-gpt-export-${session?.id || "user"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setMessage("Something went wrong while exporting your data");
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    setMessage("");
    try {
      const token = getStoredToken();
      const [backendRes, frontendRes] = await Promise.all([
        fetch(`${BACKEND_URL}/user/account`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/user/delete", { method: "DELETE" }),
      ]);

      if (!frontendRes.ok || !backendRes.ok) {
        setMessage("Failed to fully delete account. Please try again or contact support.");
        return;
      }

      localStorage.removeItem("token");
      sessionStorage.clear();
      router.push("/login");
    } catch {
      setMessage("Something went wrong while deleting your account");
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  if (!session || loading) return null;

  const t = ui[lang];

  return (
    <MobileShell>
      <div className="min-h-screen pb-28" style={{ background: "var(--bg)" }}>
        <main className="mx-auto w-full max-w-[680px] px-4 py-6 sm:px-6">

          {/* Page title */}
          <div className="mb-5 flex items-center justify-between gap-3">
            <h1 className="text-[22px] font-extrabold tracking-tight text-[var(--text-1)] sm:text-[26px]">
              {t.profileTitle}
            </h1>
            <LanguageSwitcher />
          </div>

          {/* ── Profile card ─────────────────────────────────── */}
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="flex items-center gap-4">
                {/* Avatar */}
                <label className={`group relative flex h-16 w-16 cursor-pointer items-center justify-center overflow-hidden rounded-full text-white ${isEditing ? "cursor-pointer" : "cursor-default"}`}
                  style={{ background: "#c97b5a" }}>
                  {form.profileImage ? (
                    <img src={form.profileImage} alt="Profile" className="h-full w-full object-cover" />
                  ) : (
                    <span className="material-symbols-outlined text-[28px]">person</span>
                  )}
                  {isEditing && (
                    <>
                      <div className="absolute inset-0 flex items-center justify-center bg-black/35 opacity-0 transition group-hover:opacity-100">
                        <span className="material-symbols-outlined text-[18px] text-white">photo_camera</span>
                      </div>
                      <input
                        type="file" accept="image/*" className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const reader = new FileReader();
                          reader.onloadend = () => update("profileImage", reader.result as string);
                          reader.readAsDataURL(file);
                        }}
                      />
                    </>
                  )}
                </label>

                <div className="min-w-0">
                  {isEditing ? (
                    <input
                      value={form.fullName}
                      onChange={(e) => update("fullName", e.target.value)}
                      placeholder="Full name"
                      className="field-input h-9 w-full max-w-[220px] rounded-xl border px-3 text-[15px] font-bold transition"
                    />
                  ) : (
                    <h2 className="text-[17px] font-bold text-[var(--text-1)]">
                      {form.fullName || session.fullName}
                    </h2>
                  )}
                  <p className="mt-0.5 text-[13px] text-[var(--text-2)]">{session.email}</p>
                </div>
              </div>

              {!isEditing ? (
                <button
                  onClick={() => { setMessage(""); setIsEditing(true); }}
                  className="rounded-xl px-4 py-2 text-[13px] font-bold text-white transition hover:opacity-90"
                  style={{ background: "var(--brand)" }}
                >
                  Edit Profile
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={() => { if (initialForm) setForm(initialForm); setIsEditing(false); setMessage(""); }}
                    className="rounded-xl px-4 py-2 text-[13px] font-semibold transition hover:bg-[var(--surface-2)]"
                    style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-xl px-4 py-2 text-[13px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
                    style={{ background: "var(--brand)" }}
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                </div>
              )}
            </div>
          </Card>

          {/* ── Business info ─────────────────────────────────── */}
          <SectionHeader icon="business" title={t.businessStructure} />
          <Card>
            {isEditing ? (
              <>
                <InputRow label={t.organization} value={form.companyName} onChange={(v) => update("companyName", v)} />
                <Divider />
                <InputRow label={t.businessUnit} value={form.businessUnit} onChange={(v) => update("businessUnit", v)} />
                <Divider />
                <InputRow label="Job Title" value={form.jobTitle} onChange={(v) => update("jobTitle", v)} />
                <Divider />
                <InputRow label="Country" value={form.country} onChange={(v) => update("country", v)} />
                <Divider />
                <InputRow label="Phone" value={form.phone} onChange={(v) => update("phone", v)} />
              </>
            ) : (
              <>
                <FieldRow label={t.organization} value={form.companyName} />
                <Divider />
                <FieldRow label={t.businessUnit} value={form.businessUnit} />
                <Divider />
                <FieldRow label="Job Title" value={form.jobTitle} />
                <Divider />
                <FieldRow label="Country" value={form.country} />
                <Divider />
                <FieldRow label="Phone" value={form.phone} />
              </>
            )}
          </Card>

          {/* ── Preferences ───────────────────────────────────── */}
          <SectionHeader icon="tune" title={t.documentProcessing} />
          <Card>
            <SelectRow
              label={t.primaryLanguage}
              value={form.primaryLanguage}
              onChange={(v) => {
                const next = v === "si" ? "si" : "en";
                update("primaryLanguage", next);
                setLang(next);
                setStoredLanguage(next);
              }}
              options={[{ label: "English", value: "en" }, { label: "සිංහල", value: "si" }]}
            />
            <Divider />
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-[13px] font-medium text-[var(--text-1)]">{t.autoClassify}</p>
                <p className="text-[12px] text-[var(--text-3)]">Invoice / PO / DN</p>
              </div>
              <Toggle enabled={form.autoClassify} onClick={() => update("autoClassify", !form.autoClassify)} />
            </div>
          </Card>

          {/* ── Appearance ────────────────────────────────────── */}
          <SectionHeader icon="palette" title="Appearance" />
          <Card>
            <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-4">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {theme === "dark" ? "dark_mode" : "light_mode"}
                  </span>
                </div>
                <div>
                  <p className="text-[14px] font-medium text-[var(--text-1)]">Night Mode</p>
                  <p className="text-[12px] text-[var(--text-3)]">
                    {theme === "dark" ? "Dark theme active" : "Light theme active"}
                  </p>
                </div>
              </div>
              <Toggle enabled={theme === "dark"} onClick={toggleTheme} />
            </div>
          </Card>

          {/* ── Query history ─────────────────────────────────── */}
          <SectionHeader icon="history" title="Activity" />
          <Card>
            <ActionRow
              icon="query_stats"
              title="Query History"
              subtitle={queryCount !== null ? `${queryCount} saved queries` : "Loading…"}
              onClick={() => router.push("/profile/query-history")}
              right={<span className="material-symbols-outlined text-[var(--text-3)]">chevron_right</span>}
            />
          </Card>

          {/* ── Security ──────────────────────────────────────── */}
          <SectionHeader icon="security" title={t.corporateSecurity} danger />
          <Card>
            <ActionRow
              icon="key"
              title={t.changePassword}
              subtitle="Reset password via email"
              iconBg="rgba(220,38,38,0.1)"
              iconColor="#dc2626"
              onClick={() => router.push("/forgot-password")}
              right={<span className="material-symbols-outlined text-[var(--text-3)]">chevron_right</span>}
            />
            <Divider />
            <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-4">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: "var(--brand-tint)", color: "var(--brand-mid)" }}
                >
                  <span className="material-symbols-outlined text-[18px]">shield</span>
                </div>
                <div>
                  <p className="text-[14px] font-medium text-[var(--text-1)]">{t.twoFactor}</p>
                  <p className="text-[12px] text-[var(--text-3)]">Email confirmation on new devices</p>
                </div>
              </div>
              <Toggle enabled={form.twoFactorEnabled} onClick={handleToggle2FA} />
            </div>
            <Divider />
            <ActionRow
              icon="admin_panel_settings"
              title={t.sessionManagement}
              subtitle="Trusted devices and active sessions"
              iconBg="rgba(217,119,6,0.1)"
              iconColor="#d97706"
              onClick={() => router.push("/session-management")}
              right={<span className="material-symbols-outlined text-[var(--text-3)]">chevron_right</span>}
            />
          </Card>

          {/* ── Danger Zone (GDPR export/delete) ───────────────── */}
          <SectionHeader icon="warning" title="Danger Zone" danger />
          <Card>
            <ActionRow
              icon="download"
              title="Export My Data"
              subtitle="Download all your documents and query history as JSON"
              iconBg="rgba(220,38,38,0.1)"
              iconColor="#dc2626"
              onClick={handleExportData}
              right={
                exporting ? (
                  <span className="text-[12px] text-[var(--text-3)]">Exporting…</span>
                ) : (
                  <span className="material-symbols-outlined text-[var(--text-3)]">chevron_right</span>
                )
              }
            />
            <Divider />
            {!confirmDelete ? (
              <ActionRow
                icon="delete_forever"
                title="Delete Account"
                subtitle="Permanently delete your account and all associated data"
                iconBg="rgba(220,38,38,0.1)"
                iconColor="#dc2626"
                onClick={() => setConfirmDelete(true)}
                right={<span className="material-symbols-outlined text-[var(--text-3)]">chevron_right</span>}
              />
            ) : (
              <div className="px-5 py-4">
                <p className="mb-3 text-[13px] font-medium text-[var(--text-1)]">
                  This permanently deletes your account, documents, and query history. This cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="rounded-xl px-4 py-2 text-[13px] font-semibold transition hover:bg-[var(--surface-2)]"
                    style={{ border: "1px solid var(--border)", color: "var(--text-2)" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteAccount}
                    disabled={deleting}
                    className="rounded-xl px-4 py-2 text-[13px] font-bold text-white transition hover:opacity-90 disabled:opacity-60"
                    style={{ background: "#dc2626" }}
                  >
                    {deleting ? "Deleting…" : "Confirm Delete"}
                  </button>
                </div>
              </div>
            )}
          </Card>

          {message && (
            <p
              className="mt-4 rounded-xl px-4 py-2.5 text-center text-[13px] font-medium"
              style={
                message.includes("Failed") || message.includes("wrong")
                  ? { background: "rgba(220,38,38,0.08)", color: "#dc2626" }
                  : { background: "rgba(22,163,74,0.08)", color: "#16a34a" }
              }
            >
              {message}
            </p>
          )}

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="mt-6 w-full rounded-2xl py-4 text-[15px] font-bold transition hover:opacity-90"
            style={{
              border: "1px solid rgba(220,38,38,0.3)",
              background: "rgba(220,38,38,0.06)",
              color: "#dc2626",
            }}
          >
            {t.signOut}
          </button>

          <p className="mt-6 text-center text-[11px] text-[var(--text-3)]">
            SME-GPT v3.1.0 · {t.auditFooter}
          </p>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}
