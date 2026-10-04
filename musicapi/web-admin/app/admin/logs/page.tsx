"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface UsageLog {
  id: string;
  endpoint: string | null;
  model: string | null;
  prompt: string | null;
  status: string | null;
  credits_consumed: number | string | null;
  task_id: string | null;
  created_at: string;
  email: string | null;
}

function formatCredits(value: number | string | null): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(n) ? n.toLocaleString() : "—";
}

export default function LogsPage() {
  const [logs, setLogs] = useState<UsageLog[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    apiFetch<UsageLog[]>("/admin/logs")
      .then(setLogs)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const needle = q.toLowerCase();
  const filtered = logs.filter(
    (l) =>
      (l.email ?? "").toLowerCase().includes(needle) ||
      (l.endpoint ?? "").toLowerCase().includes(needle) ||
      (l.model ?? "").toLowerCase().includes(needle) ||
      (l.status ?? "").toLowerCase().includes(needle),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Usage Logs</h1>
          <p className="text-sm text-[var(--muted)]">Generation requests, newest first (up to 200)</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by user, endpoint, model or status…"
          className="rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
        />
      </div>

      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Endpoint</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Credits</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((l) => (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {new Date(l.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{l.email ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{l.endpoint ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">{l.model ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        l.status === "complete"
                          ? "bg-emerald-500/15 text-emerald-300"
                          : l.status === "error" || l.status === "failed"
                            ? "bg-red-500/15 text-red-300"
                            : "bg-white/10 text-[var(--muted)]"
                      }`}
                    >
                      {l.status ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatCredits(l.credits_consumed)}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">
                    No usage logs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
