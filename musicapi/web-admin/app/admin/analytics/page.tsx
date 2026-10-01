"use client";

import { useCallback, useEffect, useState } from "react";
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
  by_endpoint: (Agg & { endpoint: string })[];
  by_model: (Agg & { model: string })[];
  by_user: (Agg & { user_id: string; email: string })[];
  series: (Agg & { day: string })[];
}

const RANGES = [7, 30, 90];

function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

function rate(a: Agg): string {
  if (a.count === 0) return "—";
  return `${((a.success / a.count) * 100).toFixed(1)}%`;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    apiFetch<Analytics>(`/admin/analytics?days=${days}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [days]);

  useEffect(load, [load]);

  const t = data?.totals;
  const maxRevenue = Math.max(1, ...(data?.series ?? []).map((s) => s.revenue));

  const cards = [
    { label: "Requests", value: t ? String(t.count) : "—" },
    { label: "Success rate", value: t ? rate(t) : "—" },
    { label: "Failed", value: t ? String(t.failed) : "—" },
    { label: "Credits spent", value: t ? String(t.credits) : "—" },
    { label: "Revenue", value: t ? usd(t.revenue) : "—" },
  ];

  const tables: Array<{ title: string; head: string; rows: Array<Agg & { label: string }> }> = data
    ? [
        { title: "By endpoint", head: "Endpoint", rows: data.by_endpoint.map((r) => ({ ...r, label: r.endpoint })) },
        { title: "By model", head: "Model", rows: data.by_model.map((r) => ({ ...r, label: r.model })) },
        { title: "By user", head: "User", rows: data.by_user.map((r) => ({ ...r, label: r.email })) },
      ]
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-[var(--muted)]">
            Usage, success/failure and revenue trends per endpoint, model and user
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              className={`rounded-md px-3 py-1 text-xs font-semibold ${
                days === r ? "grad-bg text-white" : "text-[var(--muted)] hover:bg-white/5"
              }`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>
      )}

      {loading && !data ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {cards.map((c) => (
              <div key={c.label} className="glass rounded-xl p-5">
                <div className="text-sm text-[var(--muted)]">{c.label}</div>
                <div className="grad-text mt-1 text-3xl font-bold">{c.value}</div>
              </div>
            ))}
          </div>

          <div className="glass rounded-xl p-5">
            <h2 className="mb-4 text-sm font-semibold text-[var(--muted)]">Revenue — last {days} days</h2>
            {data.series.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">No usage in this period.</p>
            ) : (
              <div className="flex h-40 items-end gap-1">
                {data.series.map((s) => (
                  <div key={s.day} className="flex flex-1 flex-col items-center gap-1">
                    <div
                      className="grad-bg w-full rounded-t"
                      style={{ height: `${Math.max(4, (s.revenue / maxRevenue) * 100)}%` }}
                      title={`${s.day}: ${usd(s.revenue)} · ${s.count} req · ${s.failed} failed`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {tables.map((tbl) => (
            <div key={tbl.title} className="glass overflow-hidden rounded-xl">
              <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-semibold text-[var(--muted)]">
                {tbl.title}
              </h2>
              <table className="w-full text-sm">
                <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
                  <tr>
                    <th className="px-4 py-3">{tbl.head}</th>
                    <th className="px-4 py-3 text-right">Requests</th>
                    <th className="px-4 py-3 text-right">Success</th>
                    <th className="px-4 py-3 text-right">Failed</th>
                    <th className="px-4 py-3 text-right">Credits</th>
                    <th className="px-4 py-3 text-right">Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {tbl.rows.map((r, i) => (
                    <tr key={r.label || i} className="border-t border-[var(--border)]">
                      <td className="px-4 py-3 font-medium">{r.label || "—"}</td>
                      <td className="px-4 py-3 text-right">{r.count}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{r.success}</td>
                      <td className="px-4 py-3 text-right text-red-300">{r.failed}</td>
                      <td className="px-4 py-3 text-right">{r.credits}</td>
                      <td className="px-4 py-3 text-right">{usd(r.revenue)}</td>
                    </tr>
                  ))}
                  {tbl.rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">
                        No usage in this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ))}
        </>
      ) : null}
    </div>
  );
}
