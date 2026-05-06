"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession, logoutUser, SessionUser, getStoredToken } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui, setStoredLanguage } from "@/lib/i18n";

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

type QueryHistoryItem = {
  id: string;
  company_name: string;
  question: string;
  answer: string;
  explanation: string;
  metrics: Record<string, any>;
  evidence: any[];
  source_file: string;
  created_at: string;
};

function SectionTitle({
  children,
  danger,
}: {
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <p
      className={`mt-8 mb-3 text-[12px] font-bold uppercase tracking-[0.12em] ${
        danger ? "text-red-600" : "text-[#64748b]"
      }`}
    >
      {children}
    </p>
  );
}

function Toggle({
  enabled,
  onClick,
  disabled,
}: {
  enabled: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-7 w-12 rounded-full p-[3px] transition ${
        enabled ? "bg-[#2563ff]" : "bg-slate-300"
      } ${disabled ? "cursor-not-allowed opacity-70" : ""}`}
    >
      <div
        className={`h-5 w-5 rounded-full bg-white transition ${
          enabled ? "translate-x-5" : ""
        }`}
      />
    </button>
  );
}

function FieldRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="grid gap-2 px-4 py-4 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[13px] text-[#64748b]">{label}</p>
      <p className="text-[15px] break-words font-semibold text-[#0f172a]">
        {value || "-"}
      </p>
    </div>
  );
}

function InputRow({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="grid gap-2 px-4 py-4 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[13px] text-[#64748b]">{label}</p>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || label}
        className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-[14px] text-[#0f172a] outline-none focus:border-[#2563ff] focus:ring-2 focus:ring-[#2563ff]/15"
      />
    </div>
  );
}

function SelectRow({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <div className="grid gap-2 px-4 py-4 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <p className="text-[13px] text-[#64748b]">{label}</p>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-[14px] text-[#0f172a] outline-none focus:border-[#2563ff] focus:ring-2 focus:ring-[#2563ff]/15"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function ActionRow({
  icon,
  title,
  subtitle,
  iconBg = "bg-[#eef2ff]",
  iconColor = "text-[#2563ff]",
  right,
  onClick,
}: {
  icon: string;
  title: string;
  subtitle?: string;
  iconBg?: string;
  iconColor?: string;
  right?: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between px-5 py-4 text-left"
    >
      <div className="flex items-center gap-4">
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl ${iconBg} ${iconColor}`}
        >
          <span className="material-symbols-outlined text-[20px]">{icon}</span>
        </div>
        <div>
          <p className="text-[14px] font-medium text-[#0f172a]">{title}</p>
          {subtitle && <p className="text-[12px] text-[#64748b]">{subtitle}</p>}
        </div>
      </div>
      {right}
    </button>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const [lang, setLang] = useState<AppLanguage>("en");
  const [session, setSession] = useState<SessionUser | null>(null);
  const [form, setForm] = useState<ProfileData>({
  fullName: "",
  profileImage: "",
  companyName: "",
  businessUnit: "",
  primaryLanguage: "en",
  autoClassify: true,
  twoFactorEnabled: false,
  phone: "",
  jobTitle: "",
  country: "",
});
  const [initialForm, setInitialForm] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);

  useEffect(() => {
    const load = async () => {
      setLang(getStoredLanguage());

      const currentSession = await getSession();
      if (!currentSession) {
        router.push("/login");
        return;
      }
      setSession(currentSession);

      try {
        const res = await fetch("/api/profile", {
          cache: "no-store",
        });
        const data = await res.json();

        if (res.ok && data.user) {
          const loadedData: ProfileData = {
  fullName: data.user.fullName || currentSession.fullName || "",
  profileImage: data.user.profileImage || "",
  companyName: data.user.companyName || "",
  businessUnit: data.user.businessUnit || "",
  primaryLanguage: data.user.primaryLanguage || "en",
  autoClassify: data.user.autoClassify ?? true,
  twoFactorEnabled: data.user.twoFactorEnabled ?? false,
  phone: data.user.phone || "",
  jobTitle: data.user.jobTitle || "",
  country: data.user.country || "",
};

          // If the app language was changed using the header switcher, prefer showing
          // the stored app language in the UI so the Primary Language select matches
          // the rest of the app. Do not overwrite if the user is actively editing.
          try {
            if (!isEditing) {
              loadedData.primaryLanguage = getStoredLanguage();
            }
          } catch (e) {
            // ignore
          }

          setForm(loadedData);
          setInitialForm(loadedData);
        }
      } catch (error) {
        console.error("PROFILE LOAD ERROR:", error);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [router]);

  // Listen for app-wide language changes (dispatched by LanguageSwitcher)
  useEffect(() => {
    const onAppLangChanged = (e: Event) => {
      const next = (e as CustomEvent<AppLanguage>).detail as AppLanguage;
      if (!next) return;

      // update local UI language
      setLang(next);

      // if user is not editing profile, reflect the change in the primaryLanguage field
      setForm((prev) => (isEditing ? prev : { ...prev, primaryLanguage: next }));
    };

    const onStorage = (e: StorageEvent) => {
      if (e.key === "app-language" && e.newValue) {
        const next = (e.newValue as AppLanguage) || getStoredLanguage();
        setLang(next);
        setForm((prev) => (isEditing ? prev : { ...prev, primaryLanguage: next }));
      }
    };

    window.addEventListener("app-language-changed", onAppLangChanged as EventListener);
    window.addEventListener("storage", onStorage);

    return () => {
      window.removeEventListener("app-language-changed", onAppLangChanged as EventListener);
      window.removeEventListener("storage", onStorage);
    };
  }, [isEditing]);

  useEffect(() => {
    const loadQueryHistory = async () => {
      const token = getStoredToken();

      if (!token) {
        setHistoryLoading(false);
        return;
      }

      try {
        setHistoryError("");

        const res = await fetch(`${BACKEND_URL}/query-history`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          cache: "no-store",
        });

        if (res.status === 401) {
          localStorage.removeItem("token");
          sessionStorage.removeItem("token");
          router.push("/login");
          return;
        }

        const data = await res.json();

        if (!res.ok || !data.success) {
          throw new Error(data.message || "Failed to load query history.");
        }

        setQueryHistory(data.history || []);
      } catch (error: any) {
        console.error("QUERY HISTORY LOAD ERROR:", error);
        setHistoryError(error.message || "Failed to load query history.");
      } finally {
        setHistoryLoading(false);
      }
    };

    loadQueryHistory();
  }, [router]);

  const updateField = (key: keyof ProfileData, value: string | boolean) => {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  };
  const handleProfileImageChange = (file: File | null) => {
  if (!file) return;

  const reader = new FileReader();

  reader.onloadend = () => {
    updateField("profileImage", reader.result as string);
  };

  reader.readAsDataURL(file);
};

  const handleEdit = () => {
    setMessage("");
    setIsEditing(true);
  };

  const handleCancel = () => {
    if (initialForm) {
      setForm(initialForm);
    }
    setMessage("");
    setIsEditing(false);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage("");

      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
       body: JSON.stringify({
  fullName: form.fullName,
  profileImage: form.profileImage,
  companyName: form.companyName,
  businessUnit: form.businessUnit,
  primaryLanguage: form.primaryLanguage,
  autoClassify: form.autoClassify,
  phone: form.phone,
  jobTitle: form.jobTitle,
  country: form.country,
}),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to save profile");
        return;
      }

      const updatedData: ProfileData = {
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

      setForm(updatedData);
      setInitialForm(updatedData);
      setStoredLanguage(updatedData.primaryLanguage as AppLanguage);
      setLang(updatedData.primaryLanguage as AppLanguage);
      setMessage("Profile updated successfully");
      setIsEditing(false);
    } catch (error) {
      console.error("PROFILE SAVE ERROR:", error);
      setMessage("Something went wrong");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle2FA = async () => {
    const nextValue = !form.twoFactorEnabled;

    try {
      const res = await fetch("/api/profile/two-factor", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ enabled: nextValue }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessage(data.error || "Failed to update 2FA");
        return;
      }

      updateField("twoFactorEnabled", data.twoFactorEnabled);
      setInitialForm((prev) =>
        prev ? { ...prev, twoFactorEnabled: data.twoFactorEnabled } : prev
      );

      setMessage(
        data.twoFactorEnabled
          ? "Two-factor authentication enabled"
          : "Two-factor authentication disabled"
      );
    } catch (error) {
      console.error("2FA TOGGLE ERROR:", error);
      setMessage("Failed to update two-factor authentication");
    }
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
      sessionStorage.removeItem("query_result");
      sessionStorage.removeItem("selected_query_history");
      router.push("/login");
    } catch (error) {
      console.error("LOGOUT ERROR:", error);
      router.push("/login");
    }
  };

  if (!session || loading) return null;

  const t = ui[lang];

  return (
    <MobileShell>
      <div className="min-h-screen bg-[#f6f7fb] pb-24">
        <main className="mx-auto w-full max-w-[980px] px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h1 className="text-[24px] font-extrabold tracking-tight text-[#0f172a] sm:text-[28px]">
              {t.profileTitle}
            </h1>
            <LanguageSwitcher />
          </div>

          <div className="rounded-[20px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="relative">
  <label className="group relative flex h-16 w-16 cursor-pointer items-center justify-center overflow-hidden rounded-full bg-[#f7b092] text-white">
    {form.profileImage ? (
      <img
        src={form.profileImage}
        alt="Profile"
        className="h-full w-full object-cover"
      />
    ) : (
      <span className="material-symbols-outlined text-[28px]">
        person
      </span>
    )}

    {isEditing && (
      <div className="absolute inset-0 flex items-center justify-center bg-black/35 opacity-0 transition group-hover:opacity-100">
        <span className="material-symbols-outlined text-[20px] text-white">
          photo_camera
        </span>
      </div>
    )}

    {isEditing && (
      <input
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) =>
          handleProfileImageChange(e.target.files?.[0] || null)
        }
      />
    )}
  </label>
</div>

<div className="min-w-0">
  {isEditing ? (
  <div className="flex flex-col gap-2">
    <label className="text-[12px] font-medium text-[#64748b]">
      User Name
    </label>

    <input
      value={form.fullName}
      onChange={(e) => updateField("fullName", e.target.value)}
      placeholder="User name"
      className="h-10 w-full max-w-[260px] rounded-xl border border-slate-200 bg-white px-3 text-[15px] font-bold text-[#0f172a] outline-none focus:border-[#2563ff] focus:ring-2 focus:ring-[#2563ff]/15"
    />
  </div>
) : (
    <h2 className="truncate text-[18px] font-bold text-[#0f172a]">
      {form.fullName || session.fullName}
    </h2>
  )}

  <p className="mt-1 truncate text-[13px] text-[#64748b]">
    {session.email}
  </p>
</div>
              </div>

              {!isEditing ? (
                <button
                  type="button"
                  onClick={handleEdit}
                  className="rounded-xl bg-[#07122f] px-4 py-2 text-[13px] font-bold text-white"
                >
                  Edit Profile
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-[13px] font-bold text-[#64748b]"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-xl bg-[#07122f] px-4 py-2 text-[13px] font-bold text-white"
                  >
                    {saving ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              )}
            </div>
          </div>

          <SectionTitle>{t.businessStructure}</SectionTitle>
          <div className="overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-sm">
            {isEditing ? (
              <>
                <InputRow
                  label={t.organization}
                  value={form.companyName}
                  onChange={(value) => updateField("companyName", value)}
                  placeholder="Organization"
                />
                <div className="border-t" />
                <InputRow
                  label={t.businessUnit}
                  value={form.businessUnit}
                  onChange={(value) => updateField("businessUnit", value)}
                  placeholder="Business Unit"
                />
            
                <div className="border-t" />
                <InputRow
                  label="Phone"
                  value={form.phone}
                  onChange={(value) => updateField("phone", value)}
                  placeholder="Phone"
                />
                <div className="border-t" />
                <InputRow
                  label="Job Title"
                  value={form.jobTitle}
                  onChange={(value) => updateField("jobTitle", value)}
                  placeholder="Job Title"
                />
                <div className="border-t" />
                <InputRow
                  label="Country"
                  value={form.country}
                  onChange={(value) => updateField("country", value)}
                  placeholder="Country"
                />
              </>
            ) : (
              <>
                <FieldRow label={t.organization} value={form.companyName} />
                <div className="border-t" />
                <FieldRow label={t.businessUnit} value={form.businessUnit} />

                <div className="border-t" />
                <FieldRow label="Phone" value={form.phone} />
                <div className="border-t" />
                <FieldRow label="Job Title" value={form.jobTitle} />
                <div className="border-t" />
                <FieldRow label="Country" value={form.country} />
              </>
            )}
          </div>

          <SectionTitle>{t.documentProcessing}</SectionTitle>
          <div className="overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-sm">
            <SelectRow
              label={t.primaryLanguage}
              value={form.primaryLanguage}
              onChange={(value) => {
                const nextLang: AppLanguage = value === "si" ? "si" : "en";
                updateField("primaryLanguage", nextLang);
                setLang(nextLang);
                setStoredLanguage(nextLang);
                setForm((prev) => ({
                  ...prev,
                  primaryLanguage: nextLang,
                }));
              }}
              options={[
                { label: "English", value: "en" },
                { label: "සිංහල", value: "si" },
              ]}
            />
            <div className="border-t" />
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-[13px] text-[#64748b]">{t.autoClassify}</p>
                <p className="text-[15px] font-semibold text-[#0f172a]">
                  Invoice / PO / DN
                </p>
              </div>
              <Toggle
                enabled={form.autoClassify}
                onClick={() => updateField("autoClassify", !form.autoClassify)}
              />
            </div>
          </div>

          {message && (
            <p className="mt-4 text-center text-[13px] text-[#2563ff]">
              {message}
            </p>
          )}

          <SectionTitle>Query History</SectionTitle>
          <div className="overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-sm">
            <ActionRow
              icon="history"
              title="Query History"
              subtitle={
                historyLoading
                  ? "Loading query history..."
                  : historyError
                  ? historyError
                  : `${queryHistory.length} saved queries`
              }
              onClick={() => router.push("/profile/query-history")}
              right={
                <span className="material-symbols-outlined text-[#94a3b8]">
                  chevron_right
                </span>
              }
            />
          </div>

          <SectionTitle danger>{t.corporateSecurity}</SectionTitle>
          <div className="overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-sm">
            <ActionRow
              icon="key"
              title={t.changePassword}
              subtitle="Reset password by email"
              onClick={() => router.push("/forgot-password")}
              right={
                <span className="material-symbols-outlined text-[#94a3b8]">
                  chevron_right
                </span>
              }
              iconBg="bg-[#fee2e2]"
              iconColor="text-red-500"
            />
            <div className="border-t" />
            <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#eef2ff] text-[#2563ff]">
                  <span className="material-symbols-outlined text-[20px]">
                    shield
                  </span>
                </div>
                <div>
                  <p className="text-[14px] font-medium text-[#0f172a]">
                    {t.twoFactor}
                  </p>
                  <p className="text-[12px] text-[#64748b]">
                    Require email confirmation on new devices
                  </p>
                </div>
              </div>
              <Toggle enabled={form.twoFactorEnabled} onClick={handleToggle2FA} />
            </div>
            <div className="border-t" />
            <ActionRow
              icon="admin_panel_settings"
              title={t.sessionManagement}
              subtitle="Manage trusted devices and login sessions"
              onClick={() => router.push("/session-management")}
              right={
                <span className="material-symbols-outlined text-[#94a3b8]">
                  chevron_right
                </span>
              }
              iconBg="bg-[#fef3c7]"
              iconColor="text-[#d97706]"
            />
          </div>

          <button
            onClick={handleLogout}
            className="mt-8 w-full rounded-[20px] border border-red-300 bg-[#fff5f5] py-4 text-[15px] font-bold text-red-600 sm:text-[16px]"
          >
            {t.signOut}
          </button>

          <div className="mt-6 text-center text-[11px] text-[#94a3b8]">
            <p>SME-GPT v3.1.0 Enterprise</p>
            <p className="mt-1">{t.auditFooter}</p>
          </div>
        </main>

        <BottomNav />
      </div>
    </MobileShell>
  );
}