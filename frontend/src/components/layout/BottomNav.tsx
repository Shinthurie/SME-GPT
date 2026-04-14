"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AppLanguage, getStoredLanguage, ui } from "@/lib/i18n";

export default function BottomNav() {
  const pathname = usePathname();
  const [lang, setLang] = useState<AppLanguage>("en");

  useEffect(() => {
    setLang(getStoredLanguage());
  }, []);

  const t = ui[lang];

  const items = [
    { label: t.overview, icon: "dashboard", href: "/dashboard" },
    { label: t.files, icon: "folder", href: "/repository" },
    { label: t.query, icon: "query_stats", href: "/query" },
    { label: t.settings, icon: "settings", href: "/profile" },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto w-full max-w-[1180px]">
        <div className="grid grid-cols-4 px-2 py-2">
          {items.map((item) => {
            const active = pathname === item.href;

            return (
              <Link
                key={item.label}
                href={item.href}
                className={`flex flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-center text-[10px] font-medium transition sm:text-[11px] ${
                  active
                    ? "text-[#2563ff]"
                    : "text-[#94a3b8] hover:bg-slate-50"
                }`}
              >
                <span className="material-symbols-outlined text-[20px] sm:text-[22px]">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}