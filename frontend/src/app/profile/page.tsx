"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MobileShell from "@/components/layout/MobileShell";
import BottomNav from "@/components/layout/BottomNav";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import { getSession, logoutUser, SessionUser } from "@/lib/auth";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";
import { setStoredLanguage } from "@/lib/i18n";

type ProfileData = {
  companyName: string;
  businessUnit: string;
  department: string;
  primaryLanguage: string;
  autoClassify: boolean;
  twoFactorEnabled: boolean;
  phone: string;
  jobTitle: string;
  country: string;
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
      <p className="text-[15px] font-semibold text-[#0f172a] break-words">
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
    companyName: "",
    businessUnit: "",
    department: "",
    primaryLanguage: "en",
    autoClassify: true,
    twoFactorEnabled: false,
    phone: "",
    jobTitle: "",
    country: "",
  });
  const [initialForm, setInitialForm] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [isEditing, setIsEditing] = useState(false);

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
        const res = await fetch("/api/profile");
        const data = await res.json();

        if (res.ok && data.user) {
          const loadedData: ProfileData = {
            companyName: data.user.companyName || "",
            businessUnit: data.user.businessUnit || "",
            department: data.user.department || "",
            primaryLanguage: data.user.primaryLanguage || "en",
            autoClassify: data.user.autoClassify ?? true,
            twoFactorEnabled: data.user.twoFactorEnabled ?? false,
            phone: data.user.phone || "",
            jobTitle: data.user.jobTitle || "",
            country: data.user.country || "",
          };

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

  const updateField = (key: keyof ProfileData, value: string | boolean) => {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
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
          companyName: form.companyName,
          businessUnit: form.businessUnit,
          department: form.department,
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

      setForm((prev) => ({
        ...prev,
        companyName: data.user.companyName || "",
        businessUnit: data.user.businessUnit || "",
        department: data.user.department || "",
        primaryLanguage: data.user.primaryLanguage || "en",
        autoClassify: data.user.autoClassify ?? true,
        phone: data.user.phone || "",
        jobTitle: data.user.jobTitle || "",
        country: data.user.country || "",
      }));

      setInitialForm((prev) =>
        prev
          ? {
              ...prev,
              companyName: data.user.companyName || "",
              businessUnit: data.user.businessUnit || "",
              department: data.user.department || "",
              primaryLanguage: data.user.primaryLanguage || "en",
              autoClassify: data.user.autoClassify ?? true,
              phone: data.user.phone || "",
              jobTitle: data.user.jobTitle || "",
              country: data.user.country || "",
            }
          : prev
      );
      setStoredLanguage(form.primaryLanguage as AppLanguage);
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
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#f7b092] text-white">
                    <span className="material-symbols-outlined text-[28px]">
                      person
                    </span>
                  </div>
                  <div className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full bg-[#2563ff] text-white shadow">
                    <span className="material-symbols-outlined text-[14px]">
                      verified
                    </span>
                  </div>
                </div>

                <div className="min-w-0">
                  <h2 className="truncate text-[18px] font-bold text-[#0f172a]">
                    {session.fullName}
                  </h2>
                  <p className="truncate text-[13px] text-[#64748b]">
                    {session.email}
                  </p>
                  <span className="mt-2 inline-block rounded-full bg-[#e0edff] px-3 py-1 text-[10px] font-bold text-[#2563ff]">
                    {t.adminAccess}
                  </span>
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
                  label={t.department}
                  value={form.department}
                  onChange={(value) => updateField("department", value)}
                  placeholder="Department"
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
                <FieldRow label={t.department} value={form.department} />
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
            onClick={async () => {
              await logoutUser();
              router.push("/login");
            }}
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