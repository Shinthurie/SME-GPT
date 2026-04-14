"use client";

import { useRouter } from "next/navigation";

type AppHeaderProps = {
  title: string;
  subtitle?: string;
  showBack?: boolean;
};

export default function AppHeader({
  title,
  subtitle,
  showBack = false,
}: AppHeaderProps) {
  const router = useRouter();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur transition-all duration-300">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-3 px-4 py-4">
        {showBack ? (
          <button
            onClick={() => router.back()}
            className="flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-slate-100"
          >
            <span className="material-symbols-outlined text-slate-700">
              arrow_back
            </span>
          </button>
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#135bec] text-white shadow-sm">
            <span className="text-sm font-bold">S</span>
          </div>
        )}

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-bold text-slate-900">
            {title}
          </h1>
          {subtitle && (
            <p className="truncate text-sm text-slate-500">{subtitle}</p>
          )}
        </div>

        <button
          onClick={() => alert("Notifications panel can be added next.")}
          className="flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-slate-100"
        >
          <span className="material-symbols-outlined text-slate-700">
            notifications
          </span>
        </button>
      </div>
    </header>
  );
}