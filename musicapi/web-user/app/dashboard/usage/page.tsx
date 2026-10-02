"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  addDays,
  DateRangePicker,
  defaultUsageRange,
  formatShortDate,
  rangeDays,
  type UsageRange,
} from "@/components/usage/date-range-picker";
import { ExportDialog } from "@/components/usage/export-dialog";
import {
  formatMetric,
  UsageBarChart,
  type UsageMetric,
  type UsagePoint,
} from "@/components/usage/usage-bar-chart";

interface UsagePageData {
  start: string;
  end: string;
  credits_per_usd: number;
  overview: {
    total_credits: number;
    total_spend: number;
    daily: UsagePoint[];
  };
  models: Array<{
    name: string;
    count: number;
    credits: number;
    spend: number;
    daily: UsagePoint[];
  }>;
}

/** Fill missing days in the window with zeroes so the x-axis is continuous. */
function expandDaily(start: string, end: string, daily: UsagePoint[]): UsagePoint[] {
  const byDay = new Map(daily.map((d) => [d.day, d]));
  const total = Math.max(1, rangeDays({ start, end }));
  const out: UsagePoint[] = [];
  for (let i = 0; i < total; i++) {
    const day = addDays(start, i);
    out.push(byDay.get(day) ?? { day, count: 0, credits: 0, spend: 0 });
  }
  return out;
}

function MetricToggle({ metric, onChange }: { metric: UsageMetric; onChange: (m: UsageMetric) => void }) {
  return (
    <div className="flex rounded-lg bg-white/[0.06] p-1">
      {(["spend", "credits"] as const).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
            metric === key ? "bg-white/10 text-white" : "text-white/50 hover:text-white"
          }`}
        >
          {key === "spend" ? "Total Spend" : "Total Credits"}
        </button>
      ))}
    </div>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function PageSkeleton() {
  return (
    <div className="mx-auto w-full space-y-8">
      <div className="rounded-xl border border-white/5 bg-[#161618] p-6">
        <div className="h-6 w-32 animate-pulse rounded-lg bg-white/10" />
        <div className="mt-3 h-10 w-28 animate-pulse rounded-lg bg-white/10" />
        <div className="mt-6 h-[300px] w-full animate-pulse rounded-lg bg-white/5" />
      </div>
      <div className="rounded-xl border border-white/5 bg-[#161618] p-6">
        <div className="h-6 w-40 animate-pulse rounded-lg bg-white/10" />
        <div className="mt-2 h-4 w-64 animate-pulse rounded-lg bg-white/5" />
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-[320px] w-full animate-pulse rounded-xl bg-white/5" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function UsagePage() {
  const [range, setRange] = useState<UsageRange>(() => defaultUsageRange());
  const [data, setData] = useState<UsagePageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overviewMetric, setOverviewMetric] = useState<UsageMetric>("spend");
  const [endpointsMetric, setEndpointsMetric] = useState<UsageMetric>("spend");
  const [exportOpen, setExportOpen] = useState(false);
  const requestRef = useRef(0);

  const load = useCallback((r: UsageRange) => {
    const requestId = ++requestRef.current;
    return apiFetch<UsagePageData>(`/me/usage/page?start=${r.start}&end=${r.end}`)
      .then((result) => {
        if (requestRef.current === requestId) {
          setData(result);
          setError("");
        }
      })
      .catch((e: unknown) => {
        if (requestRef.current === requestId) {
          setError(e instanceof Error ? e.message : "Failed to load usage");
        }
      })
      .finally(() => {
        if (requestRef.current === requestId) setLoading(false);
      });
  }, []);

  useEffect(() => {
    // Kick off the fetch in a microtask so the effect body itself stays free of
    // synchronous state updates (react-hooks/set-state-in-effect).
    queueMicrotask(() => {
      setLoading(true);
      void load(range);
    });
  }, [load, range]);

  const overviewDaily = useMemo(
    () => (data ? expandDaily(data.start, data.end, data.overview.daily) : []),
    [data],
  );

  const overviewTotal = data
    ? overviewMetric === "spend"
      ? data.overview.total_spend
      : data.overview.total_credits
    : 0;

  return (
    <div className="relative">
      <div className="mb-6 flex flex-col items-start justify-between gap-4 lg:mb-0">
        <div>
          <h1 className="text-2xl font-bold text-white">API Usage</h1>
          <p className="mt-1 text-sm text-white/50">Track credit spend across models and API keys.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 lg:absolute lg:right-0 lg:top-0">
          <DateRangePicker value={range} onChange={setRange} />
          <button
            type="button"
            onClick={() => setExportOpen(true)}
            className="grad-bg inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-900/20"
          >
            <DownloadIcon className="h-4 w-4" />
            Export
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      {loading && !data ? (
        <div className="mt-6">
          <PageSkeleton />
        </div>
      ) : data ? (
        <div className="mt-4 space-y-8 lg:mt-16">
          {/* Overview */}
          <div className="rounded-xl border border-white/5 bg-[#161618] p-6">
            <div className="flex w-full flex-col items-start justify-between gap-4 border-b border-white/10 pb-6 md:flex-row md:items-center">
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold text-white">
                  {overviewMetric === "spend" ? "Total Spend" : "Total Credits"}
                </div>
                <p className="mt-2 text-3xl font-bold text-white">{formatMetric(overviewTotal, overviewMetric)}</p>
              </div>
              <MetricToggle metric={overviewMetric} onChange={setOverviewMetric} />
            </div>
            <div className="pt-6">
              <UsageBarChart points={overviewDaily} metric={overviewMetric} />
            </div>
          </div>

          {/* API Endpoints */}
          <div className="w-full rounded-xl border border-white/5 bg-[#161618] pb-6">
            <div className="border-b border-white/10 p-6">
              <div className="flex w-full flex-col items-start justify-between gap-4 md:flex-row md:items-center">
                <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
                  <div className="font-semibold text-white">API Endpoints</div>
                  <p className="text-sm text-white/50">Shows the top endpoints with highest usage in the selected period</p>
                </div>
                <MetricToggle metric={endpointsMetric} onChange={setEndpointsMetric} />
              </div>
            </div>

            {data.models.length > 0 ? (
              <div className="grid w-full grid-cols-1 gap-6 px-4 pt-6 md:grid-cols-2 lg:px-6">
                {data.models.map((model) => {
                  const daily = expandDaily(data.start, data.end, model.daily);
                  const total = endpointsMetric === "spend" ? model.spend : model.credits;
                  return (
                    <div key={model.name} className="rounded-xl border border-white/10 p-6 shadow-sm">
                      <div className="mb-4 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate font-medium text-white" title={model.name}>
                            {model.name}
                          </div>
                          <div className="mt-1 text-sm text-white/60">
                            {endpointsMetric === "spend" ? "Total Spend: " : "Total Credits: "}
                            {formatMetric(total, endpointsMetric)}
                          </div>
                        </div>
                      </div>
                      <div className="mb-4">
                        <UsageBarChart points={daily} metric={endpointsMetric} />
                      </div>
                      <div className="flex justify-between text-sm text-white/50">
                        <span>{formatShortDate(data.start)}</span>
                        <span>{formatShortDate(data.end)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="w-full px-6 pt-6 text-center text-white/50">
                <p>No API endpoint usage data available for the selected period.</p>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {exportOpen && <ExportDialog onClose={() => setExportOpen(false)} />}
    </div>
  );
}
