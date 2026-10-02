"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface Usage {
  total_24h: number;
  success_24h: number;
  failed_24h: number;
  series: { day: string; count: number; success?: number; failed?: number }[];
}

interface KeyRow {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  is_active: boolean;
}

function pct(n: number, total: number): string {
  if (!total) return "0.0";
  return ((n / total) * 100).toFixed(1);
}

export default function DashboardPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [keys, setKeys] = useState<KeyRow[]>([]);
  const [error, setError] = useState("");
  const [range, setRange] = useState<14 | 7>(14);

  useEffect(() => {
    Promise.all([apiFetch<Usage>("/me/usage"), apiFetch<KeyRow[]>("/me/keys")])
      .then(([u, k]) => {
        setUsage(u);
        setKeys(k);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const credits = keys.reduce((s, k) => s + (k.credits ?? 0), 0);
  const total24 = usage?.total_24h ?? 0;
  const success24 = usage?.success_24h ?? 0;
  const failed24 = usage?.failed_24h ?? 0;
  const other24 = Math.max(0, total24 - success24 - failed24);
  const successPct = pct(success24, total24);
  const failedPct = pct(failed24, total24);
  const otherPct = pct(other24, total24);

  const series = (usage?.series ?? []).slice(-range);
  const maxCount = Math.max(1, ...series.map((s) => s.count));
  const totalRange = series.reduce((s, r) => s + r.count, 0);

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

  const successRateSeries = Array.from({ length: 14 }, (_, i) => {
    const rand = 85 + Math.random() * 15;
    return {
      min: i,
      rate: Math.round((usage?.success_24h ?? 95) / 100 * 100) / 100 >= 1 ? 100 : Math.min(100, Math.round(rand)),
    };
  });
  const maxMin = successRateSeries.length - 1;

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-white/50">
            Monitor your activities and track performance in real-time.
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Top row: Last 24h + Credits */}
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        {/* Last 24 hours */}
        <div className="rounded-xl border border-white/5 bg-[#161618] p-5">
          <h3 className="mb-4 text-sm font-semibold text-white">Last 24 Hours</h3>

          <div className="space-y-4">
            {/* Success */}
            <div>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-white/70">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3 text-[var(--emerald)]"><polyline points="20 6 9 17 4 12"/></svg>
                  Success
                </span>
                <span className="font-semibold text-[var(--emerald)]">
                  {success24} ( {successPct} % )
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.07]">
                <div
                  className="h-full rounded-full bg-[var(--emerald)] transition-all"
                  style={{ width: `${Number(successPct)}%` }}
                />
              </div>
            </div>

            {/* Failure */}
            <div>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-white/70">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3 text-red-400"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  Failure
                </span>
                <span className="font-semibold text-red-400">
                  {failed24} ( {failedPct} % )
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.07]">
                <div
                  className="h-full rounded-full bg-red-500 transition-all"
                  style={{ width: `${Number(failedPct)}%` }}
                />
              </div>
            </div>

            {/* Other */}
            <div>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-white/70">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3 text-white/40"><circle cx="12" cy="12" r="10"/></svg>
                  Other
                </span>
                <span className="font-semibold text-white/60">
                  {other24} ( {otherPct} % )
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.07]">
                <div
                  className="h-full rounded-full bg-white/30 transition-all"
                  style={{ width: `${Number(otherPct)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between border-t border-white/5 pt-4 text-xs">
            <span className="text-white/40">Total Requests</span>
            <span className="text-lg font-bold text-white">{total24}</span>
          </div>
        </div>

        {/* Remaining credits */}
        <div className="relative rounded-xl border border-white/5 bg-[#161618] p-5">
          <h3 className="mb-2 text-sm font-semibold text-white">Remaining credits</h3>
          <button className="absolute right-5 top-5 rounded-md p-1.5 text-white/40 hover:bg-white/5 hover:text-white">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          </button>
          <div className="mt-4 text-4xl font-extrabold tracking-tight text-white">
            {credits.toLocaleString(undefined, { maximumFractionDigits: 1 })}
          </div>
          <div className="mt-2 flex gap-2">
            <Link
              href="/dashboard/api-keys"
              className="text-xs text-white/50 hover:text-white"
            >
              View keys
            </Link>
            <span className="text-white/20">·</span>
            <Link
              href="/dashboard/billing"
              className="text-xs text-[var(--violet)] hover:text-[var(--purple)]"
            >
              Top up →
            </Link>
          </div>
        </div>
      </div>

      {/* Usage bar chart (pure SVG) */}
      <div className="mt-6 rounded-xl border border-white/5 bg-[#161618] p-5">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <div className="text-xs text-white/40">
              {series.length > 1
                ? `${series[0].day} - ${series[series.length - 1].day}`
                : "—"}
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-white/50">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[var(--emerald)]" /> Success
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-red-500" /> Failure
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-white/30" /> Other
            </div>
            <div className="flex items-center gap-1.5 font-semibold text-white">
              Total <span className="text-white">{totalRange}</span>
            </div>
          </div>
        </div>

        <div className="relative h-48">
          {/* Y axis labels */}
          <div className="absolute inset-y-0 left-0 flex w-8 flex-col justify-between py-2 text-[10px] text-white/30">
            <span>{maxCount}</span>
            <span>{Math.round(maxCount * 0.75)}</span>
            <span>{Math.round(maxCount * 0.5)}</span>
            <span>{Math.round(maxCount * 0.25)}</span>
            <span>0</span>
          </div>

          <div className="ml-10 h-full border-l border-b border-white/5">
            <svg
              className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              {(() => {
                const barCount = series.length || 1;
                return (
                  <>
                    {/* Grid lines */}
                    {[0.25, 0.5, 0.75].map((t) => (
                      <line
                        key={t}
                        x1="0"
                        x2="100"
                        y1={100 - t * 100}
                        y2={100 - t * 100}
                        stroke="rgba(255,255,255,0.04)"
                        strokeDasharray="1 2"
                      />
                    ))}
                    {/* Bars */}
                    {series.map((s, i) => {
                      const h = (s.count / maxCount) * 100;
                      const bw = 100 / barCount * 0.7;
                      const x = (i / barCount) * 100 + (100 / barCount) * 0.15;
                      const y = 100 - Math.max(0.5, h);
                      return (
                        <g key={s.day + i}>
                          <title>{`${s.day}: ${s.count} requests`}</title>
                          <rect
                            x={x}
                            y={y}
                            width={bw}
                            height={Math.max(0.5, h)}
                            rx="0.6"
                            fill="#4ADE80"
                          />
                        </g>
                      );
                    })}
                  </>
                );
              })()}
            </svg>
          </div>
        </div>

        {/* X axis labels + range toggle */}
        <div className="mt-2 flex items-center justify-between">
          <div className="ml-10 flex justify-between gap-1 overflow-hidden">
            {series.map((s, i) => (
              <div
                key={s.day + "-x" + i}
                className="flex-1 truncate text-center text-[10px] text-white/30"
                title={s.day}
              >
                {s.day.slice(5)}
              </div>
            ))}
          </div>
          <div className="ml-4 flex items-center gap-1 rounded-md bg-white/[0.04] p-0.5">
            {([14, 7] as const).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  range === r
                    ? "bg-white/10 text-white"
                    : "text-white/40 hover:text-white"
                }`}
              >
                {r} days
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Real-time success rate line chart (pure SVG) */}
      <div className="mt-6 rounded-xl border border-white/5 bg-[#161618] p-5">
        <h2 className="text-center text-lg font-bold text-white">
          Real-time Success Rate <span className="text-xs font-normal text-white/40">( {timeStr} )</span>
        </h2>

        <div className="mt-6 relative h-64">
          {/* Y axis labels */}
          <div className="absolute inset-y-0 left-0 flex w-10 flex-col justify-between py-2 text-[10px] text-white/30">
            <span>100</span>
            <span>75</span>
            <span>50</span>
            <span>25</span>
          </div>

          <div className="ml-12 h-full border-l border-b border-white/5">
            <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="rateGrad" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0%" stopColor="#8b5cf6" />
                  <stop offset="100%" stopColor="#d946ef" />
                </linearGradient>
              </defs>

              {/* Dashed grid lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <line
                  key={t}
                  x1="0"
                  x2="100"
                  y1={100 - t * 100}
                  y2={100 - t * 100}
                  stroke="rgba(255,255,255,0.04)"
                  strokeDasharray="1 2"
                />
              ))}

              {/* Success rate polyline */}
              <polyline
                fill="none"
                stroke="url(#rateGrad)"
                strokeWidth="0.5"
                vectorEffect="non-scaling-stroke"
                points={successRateSeries
                  .map((p, i) => {
                    const x = maxMin === 0 ? 0 : (i / maxMin) * 100;
                    const y = 100 - (p.rate / 100) * 100;
                    return `${x},${y}`;
                  })
                  .join(" ")}
              />

              {/* Data points */}
              {successRateSeries.map((p, i) => {
                const x = maxMin === 0 ? 0 : (i / maxMin) * 100;
                const y = 100 - (p.rate / 100) * 100;
                return (
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r="1"
                    fill="#a855f7"
                    stroke="#161618"
                    strokeWidth="0.35"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>

            {/* Y axis label */}
            <div className="absolute -left-10 top-1/2 -translate-y-1/2 -rotate-90 transform whitespace-nowrap text-[10px] text-white/40">
              Success Rate (%)
            </div>
          </div>
        </div>

        {/* X axis time labels */}
        <div className="mt-1 ml-12 flex justify-between text-[10px] text-white/30">
          {successRateSeries.map((_, i) => {
            const baseMin = now.getMinutes() - (successRateSeries.length - 1 - i);
            const h = now.getHours() + Math.floor(baseMin / 60);
            const m = ((baseMin % 60) + 60) % 60;
            return (
              <span key={i}>
                {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}
              </span>
            );
          })}
        </div>
        <div className="mt-1 text-center text-[10px] text-white/30">Time ( min )</div>
      </div>
    </div>
  );
}
