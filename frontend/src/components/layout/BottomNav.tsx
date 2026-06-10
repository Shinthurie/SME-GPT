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
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 backdrop-blur"
      style={{
        background: "var(--surface)",
        borderTop: "1px solid var(--border)",
      }}
    >
      <div className="mx-auto w-full max-w-[1180px]">
        <div className="grid grid-cols-4 px-2 py-1.5">
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.label}
                href={item.href}
                className="flex flex-col items-center justify-center gap-0.5 rounded-xl px-2 py-2 text-center text-[10px] font-semibold transition sm:text-[11px]"
                style={{
                  color: active ? "var(--brand-mid)" : "var(--text-3)",
                }}
              >
                <span
                  className="material-symbols-outlined text-[22px]"
                  style={{
                    fontVariationSettings: active
                      ? '"FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24'
                      : '"FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24',
                  }}
                >
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
