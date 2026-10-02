"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  StackedBarChart,
  STATUS_COLORS,
  type TimelineDay,
} from "@/components/dashboard/stacked-bar-chart";
import { SuccessRateChart, type SuccessRatePoint } from "@/components/dashboard/success-rate-chart";

interface Usage {
  total_24h: number;
  success_24h: number;
  failed_24h: number;
}

interface Billing {
  credits: number;
}

interface Timeline {
  start: string;
  end: string;
  total: number;
  daily: TimelineDay[];
}

interface SuccessRateRow {
  timestamp: number;
  success: number;
  total: number;
  success_rate: number;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function clockTime(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

const CheckIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const FailIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>
);

const OtherIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5">
    <circle cx="12" cy="12" r="9" />
  </svg>
);

const BellIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const LEGEND: Array<{ key: keyof typeof STATUS_COLORS; label: string; icon: React.ReactNode }> = [
  { key: "success", label: "Success", icon: CheckIcon },
  { key: "failure", label: "Failure", icon: FailIcon },
  { key: "other", label: "Other", icon: OtherIcon },
];

function LastHoursCard({ usage }: { usage: Usage | null }) {
  const total = usage?.total_24h ?? 0;
  const success = usage?.success_24h ?? 0;
  const failed = usage?.failed_24h ?? 0;
  const other = Math.max(0, total - success - failed);
  const pct = (n: number) => (total ? ((n / total) * 100).toFixed(1) : "0.0");
  const values: Record<keyof typeof STATUS_COLORS, number> = { success, failure: failed, other };

  return (
    <div className="h-full w-full rounded-xl border border-white/5 bg-[#161618] p-4 lg:p-6">
      <div className="flex w-full items-center gap-4">
        <h3 className="text-lg font-semibold text-white">Last 24 Hours</h3>
      </div>

      <div className="mt-6 flex w-full flex-col items-start gap-10 md:mt-10">
        <div className="flex w-full flex-col items-start gap-8">
          {LEGEND.map((row) => {
            const value = values[row.key];
            const color = STATUS_COLORS[row.key];
            return (
              <div key={row.key} className="flex w-full flex-col items-start gap-2">
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct(value)}%`, backgroundColor: color }}
                  />
                </div>
                <div className="flex w-full items-center justify-between text-sm text-white/80">
                  <div className="inline-flex items-center gap-1.5" style={{ color }}>
                    {row.icon}
                    <span className="text-white/80">{row.label}</span>
                  </div>
                  <div className="inline-flex items-center gap-1">
                    <span className="text-white">{value}</span>
                    <span className="text-xs" style={{ color }}>( {pct(value)}% )</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex w-full items-center justify-between gap-2">
          <span className="text-sm text-white/80">Total Requests</span>
          <span className="text-xl font-semibold text-white">{total}</span>
        </div>
      </div>
    </div>
  );
}

function CreditsCard({ credits }: { credits: number | null }) {
  return (
    <div className="h-full w-full rounded-xl border border-white/5 bg-[#161618] p-4 lg:p-6">
      <div className="flex w-full items-center justify-between gap-4">
        <h3 className="text-lg font-semibold text-white">Remaining credits</h3>
        <button
          type="button"
          title="Set credit threshold alerts"
          className="rounded-lg p-2 text-white/40 transition hover:bg-white/5 hover:text-[var(--violet)]"
        >
          {BellIcon}
        </button>
      </div>

      <div className="mt-4 flex w-full flex-col items-start gap-10 md:mt-8">
        <div className="flex w-full flex-col items-start gap-2">
          <span className="text-4xl font-semibold text-white">{(credits ?? 0).toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}

function TimelineCard({
  data,
  range,
  onRangeChange,
}: {
  data: Timeline | null;
  range: 7 | 14;
  onRangeChange: (r: 7 | 14) => void;
}) {
  return (
    <div className="w-full rounded-xl border border-white/5 bg-[#161618]">
      <div className="flex flex-col gap-y-4 p-4">
        <div className="flex w-full items-center justify-between gap-4 text-sm text-white/80">
          <div className="flex items-center">{data ? `${data.start} - ${data.end}` : "—"}</div>
          <div className="inline-flex items-center gap-2">
            Total <span className="text-lg font-semibold text-white">{data?.total ?? 0}</span>
          </div>
        </div>
        <div className="flex w-full justify-end gap-4 text-[11px] text-white/50">
          {LEGEND.map((row) => (
            <div key={row.key} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: STATUS_COLORS[row.key] }} />
              <span className="capitalize">{row.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="px-4 pb-2">
        <StackedBarChart days={data?.daily ?? []} />
      </div>

      <div className="mx-4 border-t border-white/10" />

      <div className="flex gap-x-2 p-4">
        {([14, 7] as const).map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => onRangeChange(r)}
            className={`rounded-lg px-3 py-1 text-sm font-medium transition-colors ${
              range === r ? "bg-white/10 text-white" : "text-white/50 hover:text-white"
            }`}
          >
            {r} days
          </button>
        ))}
      </div>
    </div>
  );
}

function SuccessRateCard() {
  const [points, setPoints] = useState<SuccessRatePoint[]>([]);
  const [now, setNow] = useState(() => clockTime(new Date()));

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      apiFetch<SuccessRateRow[]>("/me/dashboard/success-rate")
        .then((rows) => {
          if (!cancelled) setPoints(rows.map((r) => ({ timestamp: r.timestamp, successRate: r.success_rate })));
        })
        .catch(() => {});
    };
    load();
    const dataTimer = setInterval(load, 60_000);
    const clockTimer = setInterval(() => setNow(clockTime(new Date())), 1_000);
    return () => {
      cancelled = true;
      clearInterval(dataTimer);
      clearInterval(clockTimer);
    };
  }, []);

  return (
    <div className="w-full rounded-xl border border-white/5 bg-[#161618] p-4 lg:p-6">
      <h2 className="flex w-full gap-1 font-semibold text-white">
        Real-time Success Rate{" "}
        <span className="text-sm font-medium text-white/40" suppressHydrationWarning>
          ({now})
        </span>
      </h2>
      <div className="mt-6 w-full md:mt-8">
        <SuccessRateChart points={points} />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [credits, setCredits] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [range, setRange] = useState<7 | 14>(14);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<Usage>("/me/usage"), apiFetch<Billing>("/me/billing")])
      .then(([u, b]) => {
        setUsage(u);
        setCredits(b.credits);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Timeline>(`/me/dashboard/timeline?days=${range}`)
      .then((d) => {
        if (!cancelled) setTimeline(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [range]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>
      <p className="mt-1 text-sm text-white/50">Monitor your activities and track performance in real-time.</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      <div className="mt-6 flex w-full flex-col items-start gap-4 lg:gap-8">
        <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2 lg:gap-8">
          <LastHoursCard usage={usage} />
          <CreditsCard credits={credits} />
        </div>

        <div className="flex w-full flex-col items-start gap-4 lg:gap-8">
          <TimelineCard data={timeline} range={range} onRangeChange={setRange} />
          <SuccessRateCard />
        </div>
      </div>
    </div>
  );
}
