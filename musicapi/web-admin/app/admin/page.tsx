"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AccountHealth {
  total: number;
  healthy: number;
  disabled: number;
  low_credits: number;
  captcha_required: number;
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
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/admin/stats")
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  if (error) return <p className="text-red-300">{error}</p>;
  if (!stats) return <p className="text-[var(--muted)]">Loading…</p>;

  const max = Math.max(1, ...stats.series.map((s) => s.count));
  const cards: Array<{ label: string; value: string }> = [
    { label: "Users", value: String(stats.users) },
    { label: "API Keys", value: String(stats.keys) },
    { label: "Suno Accounts", value: String(stats.accounts) },
    { label: "Suno Credits", value: String(stats.suno_credits.active) },
    { label: "Total Requests", value: String(stats.requests) },
    { label: "Credits Held", value: String(stats.credits) },
    { label: "Credits Spent", value: String(stats.spent) },
    { label: "Revenue", value: `$${stats.revenue.toFixed(2)}` },
  ];

  const h = stats.account_health;
  const healthChips: Array<{ label: string; value: number; cls: string }> = [
    { label: "Healthy", value: h.healthy, cls: "bg-emerald-500/15 text-emerald-300" },
    { label: "Low credits", value: h.low_credits, cls: "bg-amber-500/15 text-amber-300" },
    { label: "Captcha required", value: h.captcha_required, cls: "bg-amber-500/15 text-amber-300" },
    { label: "Disabled", value: h.disabled, cls: "bg-red-500/15 text-red-300" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-[var(--muted)]">Platform overview</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {cards.map((c) => (
          <div key={c.label} className="glass rounded-xl p-5">
            <div className="text-sm text-[var(--muted)]">{c.label}</div>
            <div className="grad-text mt-1 text-3xl font-bold">{c.value}</div>
          </div>
        ))}
      </div>

      <div className="glass rounded-xl p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">
          Suno accounts health — {h.total} total
        </h2>
        <p className="mb-4 mt-1 text-xs text-[var(--muted)]">
          Live credit pool: {stats.suno_credits.active} available of {stats.suno_credits.total} total
        </p>
        {h.total === 0 ? (
          <p className="text-sm text-[var(--muted)]">No Suno accounts configured.</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {healthChips.map((chip) => (
              <div key={chip.label} className="rounded-lg border border-white/10 px-4 py-3">
                <div className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${chip.cls}`}>
                  {chip.label}
                </div>
                <div className="mt-2 text-2xl font-bold">{chip.value}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="glass rounded-xl p-5">
        <h2 className="mb-4 text-sm font-semibold text-[var(--muted)]">Requests — last 30 days</h2>
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
      </div>
    </div>
  );
}
