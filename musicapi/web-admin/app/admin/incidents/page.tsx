"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { dateTime, num, usd } from "@/lib/format";

interface AlertItem {
  id: string;
  type: string;
  severity: "warning" | "critical";
  message: string;
  details: Record<string, unknown>;
}

interface AlertSettings {
  enabled: boolean;
  low_credits_threshold: number;
  captcha_balance_threshold: number;
  failure_rate_threshold: number;
  failure_rate_min_requests: number;
  window_minutes: number;
  queue_backlog_depth: number;
}

interface AlertReport {
  enabled: boolean;
  checked_at: string;
  thresholds: AlertSettings;
  alerts: AlertItem[];
  summary: {
    low_credits: number;
    captcha_required: number;
    captcha_balance: number | null;
    failure_rate: number | null;
    requests: number;
    failures: number;
    queue_backlog: number;
  };
}

interface Analytics {
  by_error: { reason: string; count: number }[];
}

interface SystemInfo {
  suno: {
    active: number;
    waiting: number;
    capacity: number;
    max_concurrent_per_user: number;
    max_concurrent_per_account: number;
  };
}

interface StatsInfo {
  accounts: number;
  account_health: {
    total: number;
    healthy: number;
    disabled: number;
    low_credits: number;
    captcha_required: number;
    captcha_solver: boolean;
  };
  suno_credits: { total: number; active: number };
}

const SEVERITY_TONE: Record<string, BadgeTone> = { critical: "danger", warning: "warning" };

export default function IncidentsPage() {
  const [report, setReport] = useState<AlertReport | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [stats, setStats] = useState<StatsInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [a, n, s, st] = await Promise.all([
        apiFetch<AlertReport>("/admin/alerts"),
        apiFetch<Analytics>("/admin/analytics?days=7"),
        apiFetch<SystemInfo>("/admin/system"),
        apiFetch<StatsInfo>("/admin/stats"),
      ]);
      setReport(a);
      setAnalytics(n);
      setSystem(s);
      setStats(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !report) return <LoadingState />;
  if (error && !report) return <ErrorState message={error} onRetry={load} />;

  const s = report?.summary;
  const health = stats?.account_health;
  const topErrors = (analytics?.by_error ?? []).slice(0, 12);
  const alerts = report?.alerts ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts & Incidents"
        description={`Ops pulse · live alerts, top failures and account health${
          report ? ` · checked ${dateTime(report.checked_at)}` : ""
        }`}
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            {loading ? "Checking…" : "Re-check"}
          </Button>
        }
      />

      {error && <ErrorState message={error} onRetry={load} />}

      {/* Current alerts */}
      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--muted)]">Active alerts</h2>
          {report && !report.enabled && <Badge tone="neutral">evaluation disabled</Badge>}
        </div>
        {!report ? (
          <p className="text-sm text-[var(--muted)]">No data.</p>
        ) : alerts.length === 0 ? (
          <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
            All clear — no active alerts.
          </p>
        ) : (
          <ul className="space-y-2">
            {alerts.map((a) => (
              <li
                key={a.id}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  a.severity === "critical"
                    ? "border-red-500/30 bg-red-500/10 text-red-300"
                    : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                }`}
              >
                <Badge tone={SEVERITY_TONE[a.severity] ?? "neutral"}>{a.severity}</Badge>
                <span className="ml-2">{a.message}</span>
              </li>
            ))}
          </ul>
        )}
        <Link href="/admin/settings" className="inline-block text-xs text-[var(--violet)] hover:underline">
          Alert thresholds →
        </Link>
      </Card>

      {/* Ops counters */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Queue backlog" value={String(s?.queue_backlog ?? 0)} hint="jobs waiting for a Suno slot" />
        <StatCard
          label="Failure rate"
          value={s?.failure_rate == null ? "—" : `${(s.failure_rate * 100).toFixed(1)}%`}
          hint={s ? `${num(s.failures)} / ${num(s.requests)} req (${report?.thresholds.window_minutes ?? 0}m)` : undefined}
        />
        <StatCard
          label="2Captcha"
          value={s?.captcha_balance == null ? "—" : usd(s.captcha_balance)}
          hint="solver balance"
        />
        <StatCard label="Low-credit accounts" value={String(s?.low_credits ?? 0)} hint="Suno accounts at/below floor" />
        <StatCard
          label="Suno credits (live)"
          value={num(stats?.suno_credits?.active ?? 0)}
          hint={`of ${num(stats?.suno_credits?.total ?? 0)} across pool`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Top failures */}
        <Card className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--muted)]">
              Top failures
              <span className="ml-2 font-normal opacity-70">last 7 days</span>
            </h2>
            <Link href="/admin/jobs?status=error" className="text-xs text-[var(--violet)] hover:underline">
              All failed jobs →
            </Link>
          </div>
          {topErrors.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No failures in this period.</p>
          ) : (
            <ul className="space-y-1.5">
              {topErrors.map((e, i) => (
                <li key={i} className="flex items-start justify-between gap-3 border-b border-[var(--border)] pb-1.5 last:border-0">
                  <span className="break-all font-mono text-[11px] text-[var(--muted)]" title={e.reason}>
                    {e.reason}
                  </span>
                  <span className="shrink-0 rounded-full bg-red-500/15 px-2 py-0.5 text-xs tabular-nums text-red-300">
                    {num(e.count)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Account health */}
        <Card className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--muted)]">Suno account health</h2>
            <Link href="/admin/accounts" className="text-xs text-[var(--violet)] hover:underline">
              Manage accounts →
            </Link>
          </div>
          {health ? (
            <>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                  <div className="text-xs text-[var(--muted)]">Pool</div>
                  <div className="text-xl font-bold">{num(stats?.accounts ?? 0)}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--muted)]">Healthy</div>
                  <div className="text-xl font-bold text-emerald-300">{num(health.healthy)}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--muted)]">Low credits</div>
                  <div className="text-xl font-bold text-amber-300">{num(health.low_credits)}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--muted)]">Captcha</div>
                  <div className="text-xl font-bold">{num(health.captcha_required)}</div>
                </div>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Captcha solver {health.captcha_solver ? "configured" : "missing"} · disabled {num(health.disabled)}
              </p>
            </>
          ) : (
            <p className="text-sm text-[var(--muted)]">No data.</p>
          )}

          <div className="mt-2 border-t border-[var(--border)] pt-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--muted)]">Concurrency (active / waiting / capacity)</span>
              <span className="tabular-nums">
                {num(system?.suno?.active ?? 0)} / {num(system?.suno?.waiting ?? 0)} / {num(system?.suno?.capacity ?? 0)}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              per user {num(system?.suno?.max_concurrent_per_user ?? 0)} · per account{" "}
              {num(system?.suno?.max_concurrent_per_account ?? 0)} — tune on{" "}
              <Link href="/admin/settings" className="text-[var(--violet)] hover:underline">
                Settings → Integrations
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
