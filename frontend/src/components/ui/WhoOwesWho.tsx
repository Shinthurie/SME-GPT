"use client";

import { useRouter } from "next/navigation";

type Entry = {
  document_id: string;
  document_type: string;
  supplier_name: string;
  amount: number;
  currency: string;
  date: string;
};

function Column({
  title, entries, color, emptyMsg, lang, router,
}: {
  title: string;
  entries: Entry[];
  color: string;
  emptyMsg: string;
  lang: string;
  router: ReturnType<typeof useRouter>;
}) {
  const total = entries.reduce((s, e) => s + e.amount, 0);

  return (
    <div className="flex-1 rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-[0.08em]" style={{ color }}>
          {title}
        </p>
        {entries.length > 0 && (
          <span className="text-[13px] font-extrabold" style={{ color }}>
            {entries[0].currency || "LKR"}{" "}
            {total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </span>
        )}
      </div>

      {entries.length === 0 ? (
        <p className="py-4 text-center text-[12px] text-[var(--text-3)]">{emptyMsg}</p>
      ) : (
        <div className="space-y-2">
          {entries.map((e, i) => (
            <button
              key={i}
              onClick={() => router.push(`/analysis/${e.document_id}`)}
              className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left transition hover:opacity-80"
              style={{ background: `${color}08`, border: `1px solid ${color}18` }}
            >
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold text-[var(--text-1)]">
                  {e.supplier_name}
                </p>
                <p className="text-[10px] text-[var(--text-3)]">
                  {e.document_id} · {e.date || "—"}
                </p>
              </div>
              <span className="ml-3 shrink-0 text-[13px] font-bold" style={{ color }}>
                {e.currency || "LKR"} {e.amount.toLocaleString("en-US", { minimumFractionDigits: 0 })}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function WhoOwesWho({
  receivables, payables, lang,
}: {
  receivables: Entry[];
  payables: Entry[];
  lang: string;
}) {
  const router = useRouter();

  return (
    <div>
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
        {lang === "si" ? "ලැබිය යුතු / ගෙවිය යුතු" : "Outstanding Balances"}
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Column
          title={lang === "si" ? "ඔබට ලැබිය යුතු" : "Owed to You"}
          entries={receivables}
          color="#16a34a"
          emptyMsg={lang === "si" ? "ලැබිය යුතු ශේෂ නොමැත" : "No outstanding receivables"}
          lang={lang}
          router={router}
        />
        <Column
          title={lang === "si" ? "ඔබ ගෙවිය යුතු" : "You Owe"}
          entries={payables}
          color="#dc2626"
          emptyMsg={lang === "si" ? "ගෙවිය යුතු ශේෂ නොමැත" : "No outstanding payables"}
          lang={lang}
          router={router}
        />
      </div>
    </div>
  );
}
