"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Field";
import { dateTime, num } from "@/lib/format";

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

function statusTone(status: string | null): BadgeTone {
  if (status === "complete") return "success";
  if (status === "error" || status === "failed") return "danger";
  return "neutral";
}

export default function LogsPage() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useResource<UsageLog[]>(() =>
    apiFetch<UsageLog[]>("/admin/logs"),
  );
  const logs = data ?? [];

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
      <PageHeader
        title="Usage Logs"
        description="Generation requests, newest first (up to 200)"
        actions={
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by user, endpoint, model or status…"
            aria-label="Search usage logs"
            className="w-full sm:w-72"
          />
        }
      />

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No usage logs found."
          description={logs.length ? "No rows match your search." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Time</th>
                <th scope="col" className="px-4 py-3">User</th>
                <th scope="col" className="px-4 py-3">Endpoint</th>
                <th scope="col" className="px-4 py-3">Model</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((l) => (
                <tr key={l.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(l.created_at)}
                  </td>
                  <td className="px-4 py-3">{l.email ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{l.endpoint ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">{l.model ?? "—"}</td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(l.status)}>{l.status ?? "—"}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(l.credits_consumed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
