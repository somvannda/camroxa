"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
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

interface LogPage {
  rows: UsageLog[];
  total: number;
  page: number;
  page_size: number;
}

function statusTone(status: string | null): BadgeTone {
  if (status === "complete") return "success";
  if (status === "error" || status === "failed") return "danger";
  return "neutral";
}

const PAGE_SIZE = 50;

export default function LogsPage() {
  const [status, setStatus] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [email, setEmail] = useState("");
  const [page, setPage] = useState(1);

  const { data, loading, error, reload } = useResource<LogPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (status) p.set("status", status);
      if (email) p.set("email", email);
      return apiFetch<LogPage>(`/admin/logs?${p.toString()}`);
    },
    [page, status, email],
  );

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setEmail(emailInput.trim());
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Usage Logs" description="Generation requests, newest first" />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="User email" htmlFor="log-email" className="w-full sm:w-64">
          <Input
            id="log-email"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="search by email…"
          />
        </Field>
        <Field label="Status" htmlFor="log-status">
          <Select
            id="log-status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="complete">complete</option>
            <option value="error">error</option>
          </Select>
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
          title="No usage logs found."
          description={total ? "No rows match your filters." : undefined}
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
              {rows.map((l) => (
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
