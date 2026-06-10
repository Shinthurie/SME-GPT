"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ThemeToggle from "./ThemeToggle";

type AppHeaderProps = {
  title: string;
  subtitle?: string;
  showBack?: boolean;
};

export default function AppHeader({ title, subtitle, showBack = false }: AppHeaderProps) {
  const router = useRouter();
  const [profileImage, setProfileImage] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("/api/profile", { cache: "no-store" });
        const data = await res.json();
        if (res.ok && data.user?.profileImage) setProfileImage(data.user.profileImage);
      } catch {}
    };
    load();
  }, []);

  return (
    <header
      className="sticky top-0 z-30 backdrop-blur transition-all duration-300"
      style={{
        background: "rgba(var(--surface), 0.92)",
        borderBottom: "1px solid var(--border)",
        backgroundColor: "var(--surface)",
      }}
    >
      <div className="mx-auto flex w-full max-w-3xl items-center gap-3 px-4 py-3">
        {showBack ? (
          <button
            onClick={() => router.back()}
            className="flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-[var(--surface-2)]"
          >
            <span className="material-symbols-outlined text-[20px] text-[var(--text-2)]">
              arrow_back
            </span>
          </button>
        ) : (
          <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl bg-[var(--brand)] text-white shadow-sm">
            {profileImage ? (
              <img src={profileImage} alt="Profile" className="h-full w-full object-cover" />
            ) : (
              <span className="text-sm font-bold">S</span>
            )}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-bold text-[var(--text-1)]">{title}</h1>
          {subtitle && (
            <p className="truncate text-sm text-[var(--text-2)]">{subtitle}</p>
          )}
        </div>

        <ThemeToggle />

        <button
          onClick={() => router.push("/notifications")}
          className="flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-[var(--surface-2)]"
        >
          <span className="material-symbols-outlined text-[20px] text-[var(--text-2)]">
            notifications
          </span>
        </button>
      </div>
    </header>
  );
}
