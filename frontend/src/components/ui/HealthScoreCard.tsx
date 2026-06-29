"use client";

type HealthScore = {
  net: number;
  trend_pct: number;
  color: "green" | "red";
  this_month: string;
};

export default function HealthScoreCard({
  health, lang, currency = "LKR",
}: {
  health: HealthScore;
  lang: string;
  currency?: string;
}) {
  const isPositive = health.net >= 0;
  const trendUp    = health.trend_pct > 0;
  const trendZero  = health.trend_pct === 0;

  const bg    = isPositive ? "rgba(22,163,74,0.06)"  : "rgba(220,38,38,0.06)";
  const border= isPositive ? "rgba(22,163,74,0.2)"   : "rgba(220,38,38,0.2)";
  const color = isPositive ? "#16a34a"                : "#dc2626";

  return (
    <div className="rounded-2xl p-5" style={{ background: bg, border: `1px solid ${border}` }}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.08em]" style={{ color }}>
            {lang === "si" ? "මාසික ශේෂ ස්ථානය" : "Net Position This Month"}
          </p>
          <p className="mt-1.5 text-[28px] font-extrabold leading-none" style={{ color }}>
            {isPositive ? "+" : ""}{currency} {Math.abs(health.net).toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </p>
          <p className="mt-1 text-[12px]" style={{ color }}>
            {lang === "si" ? "මාසය:" : "Month:"} {health.this_month}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span
            className="flex h-12 w-12 items-center justify-center rounded-2xl text-white"
            style={{ background: color }}
          >
            <span className="material-symbols-outlined text-[24px]">
              {isPositive ? "trending_up" : "trending_down"}
            </span>
          </span>
          {!trendZero && (
            <span className="text-[11px] font-bold" style={{ color }}>
              {trendUp ? "▲" : "▼"} {Math.abs(health.trend_pct)}%{" "}
              <span className="font-normal opacity-70">
                {lang === "si" ? "vs ගිය මාසය" : "vs last month"}
              </span>
            </span>
          )}
          {trendZero && (
            <span className="text-[11px] opacity-60">
              {lang === "si" ? "මාරුවක් නැත" : "No change"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
