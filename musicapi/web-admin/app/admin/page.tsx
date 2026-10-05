"use client";

import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, StatCard } from "@/components/ui/Card";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { num, usd } from "@/lib/format";

interface AccountHealth {
  total: number;
  healthy: number;
  disabled: number;
  low_credits: number;
  captcha_required: number;
  /** A 2Captcha key is configured, so captcha requirements are solved automatically. */
  captcha_solver: boolean;
}

interface Stats {
  users: number;
  keys: number;
  requests: number;
  credits: number;
  spent: number;
  revenue: number;
  credits_per_usd: number;
  accounts: number;
  account_health: AccountHealth;
  suno_credits: { total: number; active: number };
  series: { day: string; count: number }[];
}

export default function AdminDashboard() {
  const { data: stats, loading, error, reload } = useResource<Stats>(() =>
    apiFetch<Stats>("/admin/stats"),
  );

  if (loading) return <LoadingState />;
  if (error || !stats) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" description="Platform overview" />
        <ErrorState message={error || "Failed to load"} onRetry={reload} />
      </div>
    );
  }

  const max = Math.max(1, ...stats.series.map((s) => s.count));
  const cards: Array<{ label: string; value: string }> = [
    { label: "Users", value: num(stats.users) },
    { label: "API Keys", value: num(stats.keys) },
    { label: "Suno Accounts", value: num(stats.accounts) },
    { label: "Suno Credits", value: num(stats.suno_credits.active) },
    { label: "Total Requests", value: num(stats.requests) },
    { label: "Credits Held", value: num(stats.credits) },
    { label: "Credits Spent", value: num(stats.spent) },
    { label: "Revenue", value: usd(stats.revenue) },
  ];

  const h = stats.account_health;
  const healthChips: Array<{ label: string; value: number; tone: BadgeTone }> = [
    { label: "Healthy", value: h.healthy, tone: "success" },
    { label: "Low credits", value: h.low_credits, tone: "warning" },
    h.captcha_solver
      ? { label: "Captcha (auto-solve)", value: h.captcha_required, tone: "info" }
      : { label: "Captcha required", value: h.captcha_required, tone: "warning" },
    { label: "Disabled", value: h.disabled, tone: "danger" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader title="Dashboard" description="Platform overview" />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} />
        ))}
      </div>

      <Card className="p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">
          Suno accounts health — {num(h.total)} total
        </h2>
        <p className="mb-4 mt-1 text-xs text-[var(--muted)]">
          Live credit pool: {num(stats.suno_credits.active)} available of{" "}
          {num(stats.suno_credits.total)} total
        </p>
        {h.total === 0 ? (
          <p className="text-sm text-[var(--muted)]">No Suno accounts configured.</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {healthChips.map((chip) => (
              <div key={chip.label} className="rounded-lg border border-white/10 px-4 py-3">
                <Badge tone={chip.tone}>{chip.label}</Badge>
                <div className="mt-2 text-2xl font-bold">{num(chip.value)}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 text-sm font-semibold text-[var(--muted)]">
          Requests — last 30 days
        </h2>
        <div className="flex h-40 items-end gap-1">
          {stats.series.map((s) => (
            <div key={s.day} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="grad-bg w-full rounded-t"
                style={{ height: `${Math.max(4, (s.count / max) * 100)}%` }}
                title={`${s.day}: ${s.count}`}
              />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
