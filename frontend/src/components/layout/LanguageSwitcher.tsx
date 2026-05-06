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
    // notify other client components about the language change so they can update immediately
    try {
      window.dispatchEvent(new CustomEvent("app-language-changed", { detail: next }));
    } catch (e) {
      // ignore if dispatch fails in some environments
    }
    // Also perform a short-delayed full reload so pages that rely on a reload to
    // pick up the change (SSR or pages that don't listen to the event) will update.
    // Keep the delay small to allow other listeners/storage to process first.
    setTimeout(() => {
      try {
        window.location.reload();
      } catch (e) {
        // ignore
      }
    }, 50);
  };

  return (
    <div className="inline-flex rounded-full border border-[#d7e2ff] bg-[#eef4ff] p-1 shadow-sm">
      <button
        onClick={() => handleChange("en")}
        className={`rounded-full px-3 py-1 text-xs font-bold transition ${
          lang === "en" ? "bg-white text-[#2563ff] shadow-sm" : "text-[#6b7c97]"
        }`}
      >
        EN
      </button>
      <button
        onClick={() => handleChange("si")}
        className={`rounded-full px-3 py-1 text-xs font-bold transition ${
          lang === "si" ? "bg-white text-[#2563ff] shadow-sm" : "text-[#6b7c97]"
        }`}
      >
        සි
      </button>
    </div>
  );
}