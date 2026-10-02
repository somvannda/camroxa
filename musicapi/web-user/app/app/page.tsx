"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Usage {
  total_24h: number;
  success_24h: number;
  failed_24h: number;
  series: { day: string; count: number }[];
}

interface KeyRow {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  is_active: boolean;
}

export default function DashboardPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [keys, setKeys] = useState<KeyRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<Usage>("/me/usage"), apiFetch<KeyRow[]>("/me/keys")])
      .then(([u, k]) => {
        setUsage(u);
        setKeys(k);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const credits = keys.reduce((s, k) => s + (k.credits ?? 0), 0);
  const successRate = usage && usage.total_24h > 0 ? Math.round((usage.success_24h / usage.total_24h) * 100) : 100;
  const maxCount = usage ? Math.max(1, ...usage.series.map((s) => s.count)) : 1;

  const stats = [
    { label: "Remaining credits", value: String(credits), accent: "text-[var(--emerald)]" },
    { label: "Requests (24h)", value: String(usage?.total_24h ?? 0), accent: "grad-text" },
    { label: "Success (24h)", value: String(usage?.success_24h ?? 0), accent: "text-[var(--emerald)]" },
    { label: "Failed (24h)", value: String(usage?.failed_24h ?? 0), accent: "text-red-400" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">Your AI music API workspace.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="glass rounded-2xl p-5">
            <div className="text-sm text-[var(--muted)]">{s.label}</div>
            <div className={`mt-1 text-3xl font-extrabold ${s.accent}`}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="glass rounded-2xl p-6">
          <div className="mb-3 text-sm font-semibold text-[var(--muted)]">Real-time success rate</div>
          <div className="flex items-center gap-4">
            <div className="text-4xl font-extrabold text-[var(--emerald)]">{successRate}%</div>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-[var(--emerald)]" style={{ width: `${successRate}%` }} />
            </div>
          </div>
        </div>

        <div className="glass rounded-2xl p-6">
          <div className="mb-3 text-sm font-semibold text-[var(--muted)]">Usage — last 30 days</div>
          <div className="flex h-32 items-end gap-1">
            {(usage?.series ?? []).map((s) => (
              <div key={s.day} className="group relative flex-1">
                <div
                  className="grad-bg w-full rounded-t transition-opacity group-hover:opacity-80"
                  style={{ height: `${Math.max(4, (s.count / maxCount) * 100)}%` }}
                />
              </div>
            ))}
            {(!usage || usage.series.length === 0) && (
              <div className="text-sm text-[var(--muted)]">No usage yet.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
