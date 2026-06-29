"use client";

import { useRouter } from "next/navigation";

type FeedItem = {
  event_type: string;
  content: string;
  created_at: string;
};

const EVENT_ICONS: Record<string, { icon: string; color: string }> = {
  DOCUMENT_SAVED:    { icon: "save",           color: "#16a34a" },
  DOCUMENT_UPDATED:  { icon: "edit",           color: "#2252b5" },
  DOCUMENT_DELETED:  { icon: "delete",         color: "#dc2626" },
  QUERY_EXECUTED:    { icon: "search",         color: "#7c3aed" },
  DOCUMENT_UPLOAD:   { icon: "upload_file",    color: "#ea6c0a" },
  LOGIN_SUCCESS:     { icon: "login",          color: "#16a34a" },
  LOGOUT:            { icon: "logout",         color: "#64748b" },
  PASSWORD_RESET:    { icon: "lock_reset",     color: "#ea6c0a" },
  TWO_FACTOR_UPDATE: { icon: "security",       color: "#2252b5" },
  ACCOUNT_DELETED:   { icon: "person_remove",  color: "#dc2626" },
  SIGNUP:            { icon: "person_add",     color: "#16a34a" },
};

const SINHALA_EVENTS: Record<string, string> = {
  DOCUMENT_SAVED:    "ලේඛනය සුරකිනු ලැබිණි",
  DOCUMENT_UPDATED:  "ලේඛනය යාවත්කාලීන කෙරිණි",
  DOCUMENT_DELETED:  "ලේඛනය මකා දමන ලදී",
  QUERY_EXECUTED:    "විමසුමක් ඉටු කෙරිණි",
  DOCUMENT_UPLOAD:   "ලේඛනය ඇතුළත් කෙරිණි",
  LOGIN_SUCCESS:     "ලොගින් වෙනු ලැබිණි",
  LOGOUT:            "ලොගවුට් විය",
};

function timeAgo(isoStr: string, lang: string): string {
  if (!isoStr) return "";
  try {
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1)  return lang === "si" ? "දැන්"          : "just now";
    if (mins < 60) return lang === "si" ? `${mins}min`    : `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)  return lang === "si" ? `${hrs}h`       : `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return lang === "si" ? `${days} දිනකට` : `${days}d ago`;
  } catch {
    return "";
  }
}

function extractDocId(content: string): string | null {
  const m = content.match(/document_id=([^\s,]+)/);
  return m ? m[1] : null;
}

export default function ActivityFeed({
  items, lang,
}: {
  items: FeedItem[];
  lang: string;
}) {
  const router = useRouter();

  if (!items || items.length === 0) return null;

  return (
    <div className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
        {lang === "si" ? "මෑත ක්‍රියාකාරකම්" : "Recent Activity"}
      </p>
      <div className="space-y-1">
        {items.map((item, i) => {
          const style = EVENT_ICONS[item.event_type] || { icon: "info", color: "#64748b" };
          const docId = extractDocId(item.content);
          const label = lang === "si"
            ? (SINHALA_EVENTS[item.event_type] || item.event_type)
            : item.event_type.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, l => l.toUpperCase());

          return (
            <div
              key={i}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-[var(--surface-2)]"
            >
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                style={{ background: `${style.color}12`, color: style.color }}
              >
                <span className="material-symbols-outlined text-[16px]">{style.icon}</span>
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[13px] font-semibold text-[var(--text-1)]">{label}</p>
                  {docId && (
                    <button
                      onClick={() => router.push(`/analysis/${docId}`)}
                      className="shrink-0 text-[11px] font-bold transition hover:underline"
                      style={{ color: "var(--brand-mid)" }}
                    >
                      {docId}
                    </button>
                  )}
                </div>
              </div>

              <span className="shrink-0 text-[11px] text-[var(--text-3)]">
                {timeAgo(item.created_at, lang)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
