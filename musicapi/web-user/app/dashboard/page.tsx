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

interface Profile {
  credit_alert_thresholds?: number[];
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

function CreditsCard({
  credits,
  alerts,
  onSave,
}: {
  credits: number | null;
  alerts: number[];
  onSave: (next: number[]) => Promise<void>;
}) {
  const current = credits ?? 0;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function openModal() {
    setDraft(alerts.length ? [...alerts].sort((a, b) => b - a) : []);
    setError("");
    setOpen(true);
  }

  function setAmount(i: number, v: number) {
    setDraft((d) => d.map((a, j) => (j === i ? v : a)));
  }

  async function save() {
    const seen = new Set<number>();
    for (const a of draft) {
      if (!a || a <= 0) return setError("Credit amount must be greater than 0");
      if (a >= current) return setError("Threshold must be less than current credits");
      if (seen.has(a)) return setError("Duplicate threshold amounts are not allowed");
      seen.add(a);
    }
    setSaving(true);
    setError("");
    try {
      await onSave(draft);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="h-full w-full rounded-xl border border-white/5 bg-[#161618] p-4 lg:p-6">
      <div className="flex w-full items-center justify-between gap-4">
        <h3 className="text-lg font-semibold text-white">Remaining credits</h3>
        <button
          type="button"
          onClick={openModal}
          title="Set credit threshold alerts"
          className="rounded-lg p-2 text-white/40 transition hover:bg-white/5 hover:text-[var(--violet)]"
        >
          {BellIcon}
        </button>
      </div>

      <div className="mt-4 flex w-full flex-col items-start gap-10 md:mt-8">
        <div className="flex w-full flex-col items-start gap-2">
          <span className="text-4xl font-semibold text-white">{current.toLocaleString()}</span>
        </div>
        {alerts.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-white/80">Active Alerts:</p>
            {[...alerts].sort((a, b) => b - a).map((a, i) => (
              <div key={`${a}-${i}`} className="flex items-center gap-2 text-sm">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3 text-[var(--violet)]">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                </svg>
                <span className="text-white">{a} credits</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3 text-white/40">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="m22 7-10 6L2 7" />
                </svg>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !saving && setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#14141c] p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold text-white">Credit Alert Settings</h3>
            <p className="mt-2 text-sm text-white/70">Set up to 3 credit thresholds for email notifications</p>
            <p className="mt-1 text-sm text-white/50">You&apos;ll receive an email when credits fall below each threshold</p>

            <div className="mt-5 space-y-4">
              {draft.map((amount, i) => (
                <div key={i} className="rounded-lg bg-white/[0.04] p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-medium text-white">Alert #{i + 1}</span>
                    <button
                      type="button"
                      onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}
                      className="rounded p-1 text-white/50 transition hover:bg-red-500/10 hover:text-red-300"
                      aria-label="Remove alert"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" />
                      </svg>
                    </button>
                  </div>
                  <input
                    type="number"
                    min="0"
                    placeholder="Enter credit amount (e.g., 10000)"
                    value={amount || ""}
                    onChange={(e) => setAmount(i, parseInt(e.target.value, 10) || 0)}
                    className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-[var(--violet)] placeholder:text-white/30"
                  />
                  <div className="mt-2 flex items-center gap-2 text-xs text-white/50">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 text-[var(--violet)]">
                      <rect x="2" y="4" width="20" height="16" rx="2" />
                      <path d="m22 7-10 6L2 7" />
                    </svg>
                    Email notifications enabled
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => draft.length < 3 && setDraft((d) => [...d, 0])}
                disabled={draft.length >= 3}
                className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--violet)]/40 px-4 py-3 text-sm font-medium text-[var(--violet)] transition hover:bg-[var(--violet)]/10 disabled:cursor-not-allowed disabled:border-white/10 disabled:text-white/30"
              >
                + Add Alert ({draft.length}/3)
              </button>
            </div>

            {error && <div className="mt-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setOpen(false)}
                disabled={saving}
                className="rounded-lg px-4 py-2 text-sm text-white/70 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void save()}
                disabled={saving}
                className="grad-bg rounded-lg px-6 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save Settings"}
              </button>
            </div>
          </div>
        </div>
      )}
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
  const [alerts, setAlerts] = useState<number[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<Usage>("/me/usage"),
      apiFetch<Billing>("/me/billing"),
      apiFetch<Profile>("/me/profile").catch(() => null),
    ])
      .then(([u, b, p]) => {
        if (cancelled) return;
        setUsage(u);
        setCredits(b.credits);
        if (p) setAlerts(p.credit_alert_thresholds ?? []);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveAlerts(next: number[]) {
    const updated = await apiFetch<Profile>("/me/profile", {
      method: "PUT",
      body: JSON.stringify({ credit_alert_thresholds: next }),
    });
    setAlerts(updated.credit_alert_thresholds ?? []);
  }

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
          <CreditsCard credits={credits} alerts={alerts} onSave={saveAlerts} />
        </div>

        <div className="flex w-full flex-col items-start gap-4 lg:gap-8">
          <TimelineCard data={timeline} range={range} onRangeChange={setRange} />
          <SuccessRateCard />
        </div>
      </div>
    </div>
  );
}
