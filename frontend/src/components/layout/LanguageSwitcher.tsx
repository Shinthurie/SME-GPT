"use client";

import { useEffect, useState } from "react";
import { AppLanguage, getStoredLanguage, setStoredLanguage } from "@/lib/i18n";

export default function LanguageSwitcher() {
  const [lang, setLang] = useState<AppLanguage>("en");

  useEffect(() => {
    setLang(getStoredLanguage());
  }, []);

  const handleChange = (next: AppLanguage) => {
    setLang(next);
    setStoredLanguage(next);
    try {
      window.dispatchEvent(new CustomEvent("app-language-changed", { detail: next }));
    } catch {}
    setTimeout(() => {
      try { window.location.reload(); } catch {}
    }, 50);
  };

  return (
    <div
      className="inline-flex rounded-full p-0.5"
      style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
    >
      {(["en", "si"] as AppLanguage[]).map((code) => (
        <button
          key={code}
          onClick={() => handleChange(code)}
          className="rounded-full px-3 py-1 text-xs font-bold transition"
          style={
            lang === code
              ? { background: "var(--surface)", color: "var(--brand-mid)", boxShadow: "0 1px 4px rgba(0,0,0,0.1)" }
              : { color: "var(--text-3)" }
          }
        >
          {code === "en" ? "EN" : "සි"}
        </button>
      ))}
    </div>
  );
}
