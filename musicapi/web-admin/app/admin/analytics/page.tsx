"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Agg {
  count: number;
  success: number;
  failed: number;
  credits: number;
  revenue: number;
}

interface Analytics {
  range: { days: number };
  credits_per_usd: number;
  totals: Agg;
  previous_totals?: Agg;
  by_endpoint: (Agg & { endpoint: string })[];
  by_model: (Agg & { model: string })[];
  by_user: (Agg & { user_id: string; email: string })[];
  series: (Agg & { day: string })[];
  by_error: { reason: string; count: number }[];
}

const RANGES = [7, 30, 90];

type MetricKey = "count" | "credits" | "revenue" | "failed";

const METRICS: Array<{ key: MetricKey; label: string }> = [
  { key: "count", label: "Requests" },
  { key: "credits", label: "Credits" },
  { key: "revenue", label: "Revenue" },
  { key: "failed", label: "Failures" },
];

function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

function rate(a: Agg): string {
  if (a.count === 0) return "—";
  return `${((a.success / a.count) * 100).toFixed(1)}%`;
}

function successRate(a: Agg): number | null {
  return a.count === 0 ? null : (a.success / a.count) * 100;
}

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function metricValue(a: Agg, key: MetricKey): number {
  if (key === "count") return a.count;
  if (key === "credits") return a.credits;
  if (key === "revenue") return a.revenue;
  return a.failed;
}

function formatMetric(n: number, key: MetricKey): string {
  return key === "revenue" ? usd(n) : compact(n);
}

function dayLabel(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  if (Number.isNaN(d.getTime())) return day;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Percent change vs the previous period; null when there is no baseline. */
function pctDelta(cur: number, prev: number): number | null {
  if (prev === 0) return cur === 0 ? 0 : null;
  return ((cur - prev) / prev) * 100;
}

/** Difference in percentage points between two success rates. */
function ppDelta(cur: number | null, prev: number | null): number | null {
  if (cur === null || prev === null) return null;
  return cur - prev;
}

/**
 * Fallback when the API does not return `previous_totals`: movement between the
 * two halves of the visible window. The series only contains days with traffic,
 * so this is a directional signal, not a true period comparison.
 */
function halvesDelta(series: Analytics["series"], key: MetricKey): number | null {
  if (series.length < 2) return null;
  const mid = Math.floor(series.length / 2);
  const sum = (arr: Analytics["series"]) => arr.reduce((acc, s) => acc + metricValue(s, key), 0);
  const prev = sum(series.slice(0, mid));
  const cur = sum(series.slice(mid));
  if (prev === 0) return cur === 0 ? 0 : null;
  return ((cur - prev) / prev) * 100;
}

/** Success-rate change in percentage points between the two halves. */
function halvesRateDelta(series: Analytics["series"]): number | null {
  if (series.length < 2) return null;
  const mid = Math.floor(series.length / 2);
  const rateOf = (arr: Analytics["series"]): number | null => {
    const c = arr.reduce((a, s) => a + s.count, 0);
    const ok = arr.reduce((a, s) => a + s.success, 0);
    return c === 0 ? null : (ok / c) * 100;
  };
  const prev = rateOf(series.slice(0, mid));
  const cur = rateOf(series.slice(mid));
  if (prev === null || cur === null) return null;
  return cur - prev;
}

function Sparkline({ values, className }: { values: number[]; className?: string }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const w = 100;
  const h = 28;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function StatCard({
  label,
  value,
  delta,
  deltaUnit = "%",
  goodWhenUp = true,
  deltaTitle = "vs the previous period",
  spark,
}: {
  label: string;
  value: string;
  delta?: number | null;
  deltaUnit?: string;
  goodWhenUp?: boolean;
  deltaTitle?: string;
  spark?: number[];
}) {
  const showDelta = delta !== null && delta !== undefined && Number.isFinite(delta);
  const up = (delta ?? 0) >= 0;
  const good = goodWhenUp ? up : !up;
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm text-[var(--muted)]">{label}</div>
        {showDelta && (
          <span
            className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
              good ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"
            }`}
            title={deltaTitle}
          >
            {up ? "▲" : "▼"} {Math.abs(delta).toFixed(0)}
            {deltaUnit}
          </span>
        )}
      </div>
      <div className="grad-text mt-1 text-3xl font-bold">{value}</div>
      {spark && <Sparkline values={spark} className="mt-2 h-6 w-full text-[var(--violet)] opacity-70" />}
    </div>
  );
}

function TrendChart({ series }: { series: Analytics["series"] }) {
  const [metric, setMetric] = useState<MetricKey>("count");

  if (series.length === 0) {
    return (
      <div className="glass rounded-xl p-5">
        <h2 className="mb-4 text-sm font-semibold text-[var(--muted)]">Trend</h2>
        <p className="text-sm text-[var(--muted)]">No usage in this period.</p>
      </div>
    );
  }

  const max = Math.max(1, ...series.map((s) => metricValue(s, metric)));
  const total = series.reduce((acc, s) => acc + metricValue(s, metric), 0);
  const avg = total / series.length;
  const peak = Math.max(...series.map((s) => metricValue(s, metric)));
  const isRequests = metric === "count";

  return (
    <div className="glass rounded-xl p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--muted)]">Trend</h2>
          <p className="mt-0.5 text-xs text-[var(--muted)]">
            Total {formatMetric(total, metric)} · avg/day {formatMetric(avg, metric)} · peak {formatMetric(peak, metric)}
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              aria-pressed={metric === m.key}
              className={`rounded-md px-3 py-1 text-xs font-semibold ${
                metric === m.key ? "grad-bg text-white" : "text-[var(--muted)] hover:bg-white/5"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {isRequests && (
        <div className="mb-3 flex items-center gap-4 text-xs text-[var(--muted)]">
          <span className="flex items-center gap-1.5">
            <span className="grad-bg inline-block h-2.5 w-2.5 rounded-sm" /> Success
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-400/80" /> Failed
          </span>
        </div>
      )}

      <div className="relative h-56 rounded-lg bg-black/20 p-3">
        <div className="pointer-events-none absolute inset-x-3 top-3 bottom-3 flex flex-col justify-between">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="border-t border-white/5" />
          ))}
        </div>
        <div className="relative flex h-full items-end gap-0.5 sm:gap-1">
          {series.map((s) => {
            const value = metricValue(s, metric);
            const height = value === 0 ? 0 : Math.max(2, (value / max) * 100);
            return (
              <div key={s.day} className="group relative flex h-full flex-1 flex-col justify-end">
                <div className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[#160b28] px-2.5 py-1.5 text-xs shadow-xl group-hover:block">
                  <div className="font-semibold">{dayLabel(s.day)}</div>
                  <div className="text-[var(--muted)]">
                    {s.count} req · {s.failed} failed
                  </div>
                  <div className="text-[var(--muted)]">
                    {s.credits} credits · {usd(s.revenue)}
                  </div>
                </div>
                {isRequests ? (
                  <div
                    className="flex w-full flex-col justify-end overflow-hidden rounded-t"
                    style={{ height: `${height}%` }}
                  >
                    {s.failed > 0 && (
                      <div className="w-full bg-red-400/80" style={{ height: `${(s.failed / value) * 100}%` }} />
                    )}
                    {s.success > 0 && (
                      <div className="grad-bg w-full" style={{ height: `${(s.success / value) * 100}%` }} />
                    )}
                  </div>
                ) : (
                  <div
                    className="grad-bg w-full rounded-t opacity-90 transition-opacity group-hover:opacity-100"
                    style={{ height: `${height}%` }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-2 flex justify-between text-xs text-[var(--muted)]">
        <span>{dayLabel(series[0].day)}</span>
        {series.length > 2 && <span>{dayLabel(series[Math.floor(series.length / 2)].day)}</span>}
        <span>{dayLabel(series[series.length - 1].day)}</span>
      </div>
    </div>
  );
}

type SortKey = "count" | "success" | "failed" | "credits" | "revenue";

const SORT_COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: "count", label: "Requests" },
  { key: "success", label: "Success" },
  { key: "failed", label: "Failed" },
  { key: "credits", label: "Credits" },
  { key: "revenue", label: "Revenue" },
];

function BreakdownTable({
  title,
  headLabel,
  rows,
  searchable = false,
}: {
  title: string;
  headLabel: string;
  rows: Array<Agg & { label: string }>;
  searchable?: boolean;
}) {
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [dir, setDir] = useState<"asc" | "desc">("desc");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = (needle ? rows.filter((r) => r.label.toLowerCase().includes(needle)) : rows.slice()).sort((a, b) => {
      const diff = a[sortKey] - b[sortKey];
      return dir === "asc" ? diff : -diff;
    });
    return list;
  }, [rows, q, sortKey, dir]);

  const maxRevenue = Math.max(1, ...rows.map((r) => r.revenue));
  const totalRevenue = rows.reduce((acc, r) => acc + r.revenue, 0);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setDir("desc");
    }
  }

  return (
    <div className="glass overflow-hidden rounded-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--muted)]">
          {title}
          <span className="ml-2 font-normal opacity-70">
            {rows.length} row{rows.length === 1 ? "" : "s"} · {usd(totalRevenue)}
          </span>
        </h2>
        {searchable && rows.length > 0 && (
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={`Search ${headLabel.toLowerCase()}…`}
            className="rounded-lg border border-[var(--border)] bg-black/30 px-3 py-1.5 text-xs outline-none focus:border-[var(--violet)]"
          />
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
            <tr>
              <th className="px-4 py-3">{headLabel}</th>
              {SORT_COLUMNS.map((col) => {
                const active = sortKey === col.key;
                return (
                  <th key={col.key} className="px-4 py-3 text-right">
                    <button
                      onClick={() => toggleSort(col.key)}
                      className={`inline-flex items-center gap-1 ${
                        active ? "text-[var(--foreground)]" : "hover:text-[var(--foreground)]"
                      }`}
                    >
                      {col.label}
                      <span className="text-[9px]">{active ? (dir === "asc" ? "▲" : "▼") : "↕"}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => {
              const sr = successRate(r);
              return (
                <tr key={r.label || i} className="border-t border-[var(--border)] hover:bg-white/[0.03]">
                  <td className="relative px-4 py-3 font-medium">
                    <div
                      className="absolute inset-y-1 left-2 rounded bg-[var(--violet)]/10"
                      style={{ width: `${(r.revenue / maxRevenue) * 100}%` }}
                    />
                    <span className="relative">{r.label || "—"}</span>
                  </td>
                  <td className="px-4 py-3 text-right">{r.count}</td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        sr === null
                          ? "text-[var(--muted)]"
                          : sr >= 99
                            ? "bg-emerald-500/15 text-emerald-300"
                            : sr >= 95
                              ? "bg-amber-500/15 text-amber-300"
                              : "bg-red-500/15 text-red-300"
                      }`}
                    >
                      {r.success}
                      {sr !== null && <span className="ml-1 opacity-70">{sr.toFixed(0)}%</span>}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-red-300">{r.failed}</td>
                  <td className="px-4 py-3 text-right">{r.credits}</td>
                  <td className="px-4 py-3 text-right">{usd(r.revenue)}</td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">
                  {rows.length === 0 ? "No usage in this period." : "No matching rows."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function csvCell(value: string | number): string {
  let s = String(value);
  // Neutralize spreadsheet formula injection: a user-controlled cell that starts
  // with = + - @ (or a leading tab/CR) is prefixed with a quote so Excel/Sheets
  // treats it as text.
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [reloadKey, setReloadKey] = useState(0);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Loading is toggled by the handlers (range/refresh), not inside the effect:
  // a synchronous setState in an effect body triggers cascading renders, so the
  // effect only writes state from the async callbacks.
  useEffect(() => {
    let active = true;
    apiFetch<Analytics>(`/admin/analytics?days=${days}`)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [days, reloadKey]);

  const reload = useCallback(() => {
    setLoading(true);
    setError("");
    setReloadKey((k) => k + 1);
  }, []);

  function changeRange(r: number) {
    if (r === days) return;
    setDays(r);
    setLoading(true);
    setError("");
  }

  const cards = useMemo(() => {
    if (!data) return [];
    const t = data.totals;
    const s = data.series;
    const prev = data.previous_totals;
    const deltaTitle = prev ? `vs the previous ${days} days` : "Second half of the period vs the first half";
    // Prefer the true previous-period aggregate; fall back to halves if an older
    // API response omits it.
    const pct = (key: MetricKey, cur: number) => (prev ? pctDelta(cur, metricValue(prev, key)) : halvesDelta(s, key));
    return [
      {
        label: "Requests",
        value: compact(t.count),
        delta: pct("count", t.count),
        deltaTitle,
        spark: s.map((x) => x.count),
      },
      {
        label: "Success rate",
        value: rate(t),
        delta: prev ? ppDelta(successRate(t), successRate(prev)) : halvesRateDelta(s),
        deltaUnit: "pp" as const,
        deltaTitle,
        spark: s.map((x) => (x.count ? (x.success / x.count) * 100 : 0)),
      },
      {
        label: "Failed",
        value: compact(t.failed),
        delta: pct("failed", t.failed),
        goodWhenUp: false,
        deltaTitle,
        spark: s.map((x) => x.failed),
      },
      {
        label: "Credits spent",
        value: compact(t.credits),
        delta: pct("credits", t.credits),
        deltaTitle,
        spark: s.map((x) => x.credits),
      },
      {
        label: "Revenue",
        value: usd(t.revenue),
        delta: pct("revenue", t.revenue),
        deltaTitle,
        spark: s.map((x) => x.revenue),
      },
    ];
  }, [data, days]);

  const tables = useMemo(() => {
    if (!data) return [];
    return [
      {
        title: "By endpoint",
        headLabel: "Endpoint",
        rows: data.by_endpoint.map((r) => ({ ...r, label: r.endpoint })),
        searchable: false,
      },
      {
        title: "By model",
        headLabel: "Model",
        rows: data.by_model.map((r) => ({ ...r, label: r.model })),
        searchable: false,
      },
      {
        title: "By user",
        headLabel: "User",
        rows: data.by_user.map((r) => ({ ...r, label: r.email })),
        searchable: true,
      },
    ];
  }, [data]);

  function exportCsv() {
    if (!data) return;
    const lines = ["section,label,requests,success,failed,credits,revenue"];
    const push = (section: string, label: string, r: Agg) =>
      lines.push([section, csvCell(label), r.count, r.success, r.failed, r.credits, r.revenue.toFixed(4)].join(","));
    lines.push(
      `totals,,${data.totals.count},${data.totals.success},${data.totals.failed},${data.totals.credits},${data.totals.revenue.toFixed(4)}`,
    );
    data.by_endpoint.forEach((r) => push("endpoint", r.endpoint, r));
    data.by_model.forEach((r) => push("model", r.model, r));
    data.by_user.forEach((r) => push("user", r.email, r));
    data.series.forEach((r) => push("day", r.day, r));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `camxora-analytics-${days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-[var(--muted)]">
            Usage, success/failure and revenue trends per endpoint, model and user
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportCsv}
            disabled={!data}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 disabled:opacity-40"
          >
            Export CSV
          </button>
          <button
            onClick={reload}
            disabled={loading}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--muted)] hover:bg-white/5 disabled:opacity-40"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => changeRange(r)}
                aria-pressed={days === r}
                className={`rounded-md px-3 py-1 text-xs font-semibold ${
                  days === r ? "grad-bg text-white" : "text-[var(--muted)] hover:bg-white/5"
                }`}
              >
                {r}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          <span>{error}</span>
          <button onClick={reload} className="rounded px-2 py-1 text-xs font-semibold hover:bg-white/10">
            Retry
          </button>
        </div>
      )}

      {loading && !data ? (
        <div className="space-y-8">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="glass h-24 animate-pulse rounded-xl" />
            ))}
          </div>
          <div className="glass h-72 animate-pulse rounded-xl" />
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {cards.map((c) => (
              <StatCard key={c.label} {...c} />
            ))}
          </div>

          <TrendChart series={data.series} />

          <p className="text-xs text-[var(--muted)]">
            Revenue is credits spent converted at {data.credits_per_usd} credits/USD (cheapest active pack), consistent
            with the user-facing usage view.
          </p>

          {data.by_error.length > 0 && (
            <div className="glass overflow-hidden rounded-xl">
              <div className="border-b border-[var(--border)] px-4 py-3">
                <h2 className="text-sm font-semibold text-[var(--muted)]">
                  Top failures
                  <span className="ml-2 font-normal opacity-70">
                    {data.by_error.length} reason{data.by_error.length === 1 ? "" : "s"}
                  </span>
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
                    <tr>
                      <th scope="col" className="px-4 py-3">Error</th>
                      <th scope="col" className="px-4 py-3 text-right">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_error.map((e, i) => (
                      <tr key={i} className="border-t border-[var(--border)]">
                        <td
                          className="px-4 py-3 align-top font-mono text-xs break-all"
                          title={e.reason}
                        >
                          {e.reason}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">{e.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tables.map((tbl) => (
            <BreakdownTable key={tbl.title} {...tbl} />
          ))}
        </>
      ) : null}
    </div>
  );
}
