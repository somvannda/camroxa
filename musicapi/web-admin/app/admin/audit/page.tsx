"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { dateTime, num } from "@/lib/format";

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

interface AuditPage {
  rows: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

const PAGE_SIZE = 50;

export default function AuditPage() {
  const [actionInput, setActionInput] = useState("");
  const [action, setAction] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const { data, loading, error, reload } = useResource<AuditPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (action) p.set("action", action);
      if (q) p.set("q", q);
      return apiFetch<AuditPage>(`/admin/audit?${p.toString()}`);
    },
    [page, action, q],
  );

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setAction(actionInput.trim());
    setQ(qInput.trim());
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Trail" description="Privileged actions, newest first" />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="Action" htmlFor="audit-action" className="w-full sm:w-48">
          <Input
            id="audit-action"
            value={actionInput}
            onChange={(e) => setActionInput(e.target.value)}
            placeholder="user.credits…"
          />
        </Field>
        <Field label="Actor / target / IP" htmlFor="audit-q" className="w-full sm:w-64">
          <Input
            id="audit-q"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="search…"
          />
        </Field>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {error && <ErrorState message={error} onRetry={reload} />}

      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No audit entries found."
          description={total ? "No rows match your filters." : undefined}
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
              {rows.map((a) => (
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

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-[var(--muted)]">
          <span>{num(total)} total</span>
          <span className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <span>
              Page {page} / {pages}
            </span>
            <Button
              size="sm"
              variant="secondary"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next
            </Button>
          </span>
        </div>
      )}
    </div>
  );
}
