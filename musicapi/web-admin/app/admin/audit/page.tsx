"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Field";
import { dateTime } from "@/lib/format";

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
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useResource<AuditEntry[]>(() =>
    apiFetch<AuditEntry[]>("/admin/audit"),
  );
  const entries = data ?? [];

  const needle = q.toLowerCase();
  const filtered = entries.filter(
    (a) =>
      a.action.toLowerCase().includes(needle) ||
      (a.actor_email ?? "").toLowerCase().includes(needle) ||
      (a.target_id ?? "").toLowerCase().includes(needle),
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Trail"
        description="Privileged actions, newest first (up to 200)"
        actions={
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by action, actor or target…"
            aria-label="Search audit trail"
            className="w-full sm:w-72"
          />
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No audit entries found."
          description={entries.length ? "No rows match your search." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Time</th>
                <th scope="col" className="px-4 py-3">Actor</th>
                <th scope="col" className="px-4 py-3">Action</th>
                <th scope="col" className="px-4 py-3">Target</th>
                <th scope="col" className="px-4 py-3">Details</th>
                <th scope="col" className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(a.created_at)}
                  </td>
                  <td className="px-4 py-3">{a.actor_email ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{a.action}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {a.target_type
                      ? `${a.target_type}${a.target_id ? `:${a.target_id.slice(0, 8)}` : ""}`
                      : "—"}
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
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
