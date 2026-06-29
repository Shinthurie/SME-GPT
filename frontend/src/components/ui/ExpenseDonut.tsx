"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";

type Slice = { category: string; amount: number; pct: number };

const PALETTE = [
  "#2252b5","#16a34a","#dc2626","#7c3aed","#ea6c0a","#0891b2","#64748b","#d97706",
];

const SINHALA_CATS: Record<string, string> = {
  Transport:  "ප‍ොදු ප‍ොහොසත",
  Supplies:   "කළු‍ ද්‍රව්‍ය",
  Food:       "ආහාර",
  Services:   "සේවා",
  Rent:       "කුලිය",
  Utilities:  "උපයෝගිතා",
  Marketing:  "අලෙවිකරණය",
  Other:      "වෙනත්",
};

export default function ExpenseDonut({
  data, lang, currency = "LKR",
}: {
  data: Slice[];
  lang: string;
  currency?: string;
}) {
  if (!data || data.length === 0) return null;

  const label = (cat: string) =>
    lang === "si" ? (SINHALA_CATS[cat] || cat) : cat;

  const chartData = data.map((d, i) => ({
    name:   label(d.category),
    value:  d.amount,
    pct:    d.pct,
    fill:   PALETTE[i % PALETTE.length],
  }));

  return (
    <div className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-3)]">
        {lang === "si" ? "වියදම් කාණ්ඩ" : "Expense Breakdown"}
      </p>
      <div className="flex flex-col items-center gap-4 sm:flex-row">
        {/* Donut */}
        <div style={{ width: 180, height: 180, flexShrink: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={78}
                paddingAngle={2}
                dataKey="value"
              >
                {chartData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => [
                  `${currency} ${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
                  lang === "si" ? "මුදල" : "Amount",
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Legend list */}
        <div className="flex-1 space-y-2 w-full">
          {chartData.map((d, i) => (
            <div key={i} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: d.fill }} />
                <span className="text-[12px] text-[var(--text-1)]">{d.name}</span>
              </div>
              <div className="text-right">
                <span className="text-[12px] font-bold text-[var(--text-1)]">
                  {currency} {d.value.toLocaleString("en-US", { minimumFractionDigits: 0 })}
                </span>
                <span className="ml-2 text-[10px] text-[var(--text-3)]">{d.pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
