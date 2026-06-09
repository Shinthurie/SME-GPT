"use client";

import { useTheme } from "@/lib/theme";

export default function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className={`flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-[var(--surface-2)] ${className ?? ""}`}
    >
      <span className="material-symbols-outlined text-[20px] text-[var(--text-2)]">
        {theme === "dark" ? "light_mode" : "dark_mode"}
      </span>
    </button>
  );
}
