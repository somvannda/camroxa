"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Stats {
  users: number;
  keys: number;
  requests: number;
  credits: number;
  spent: number;
  accounts: number;
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
    { label: "Total Requests", value: String(stats.requests) },
    { label: "Credits Held", value: String(stats.credits) },
    { label: "Credits Spent", value: String(stats.spent) },
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
