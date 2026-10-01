"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  details: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<AuditEntry[]>("/admin/audit")
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const needle = q.toLowerCase();
  const filtered = entries.filter(
    (a) =>
      a.action.toLowerCase().includes(needle) ||
      (a.actor_email ?? "").toLowerCase().includes(needle) ||
      (a.target_id ?? "").toLowerCase().includes(needle),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Audit Trail</h1>
          <p className="text-sm text-[var(--muted)]">Privileged actions, newest first (up to 200)</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by action, actor or target…"
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
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {new Date(a.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{a.actor_email ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{a.action}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {a.target_type ? `${a.target_type}${a.target_id ? `:${a.target_id.slice(0, 8)}` : ""}` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {a.details ? (
                      <span
                        className="block max-w-xs truncate font-mono text-xs text-[var(--muted)]"
                        title={JSON.stringify(a.details)}
                      >
                        {JSON.stringify(a.details)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">{a.ip ?? "—"}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-[var(--muted)]">
                    No audit entries found.
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
