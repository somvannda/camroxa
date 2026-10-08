"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { dateTime, num } from "@/lib/format";

interface JobRow {
  id: string;
  type: string;
  status: string;
  account_id: string | null;
  endpoint: string | null;
  model: string | null;
  credits: number | null;
  error: string | null;
  email: string | null;
  created_at: string;
  updated_at: string;
}

interface JobPage {
  rows: JobRow[];
  total: number;
  page: number;
  page_size: number;
}

const STATUS_TONES: Record<string, BadgeTone> = {
  complete: "success",
  error: "danger",
  running: "info",
  streaming: "info",
  pending: "warning",
};

const PAGE_SIZE = 25;

function JobsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [type, setType] = useState(params.get("type") ?? "");
  const [emailInput, setEmailInput] = useState(params.get("email") ?? "");
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [page, setPage] = useState(() => Math.max(1, Number(params.get("page")) || 1));
  const [auto, setAuto] = useState(false);

  const { data, loading, error, reload } = useResource<JobPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (status) p.set("status", status);
      if (type) p.set("type", type);
      if (email) p.set("email", email);
      return apiFetch<JobPage>(`/admin/jobs?${p.toString()}`);
    },
    [page, status, type, email],
  );

  // Optional live refresh so an operator can watch a queue drain.
  useEffect(() => {
    if (!auto) return;
    const t = window.setInterval(() => void reload(), 10_000);
    return () => window.clearInterval(t);
  }, [auto, reload]);

  // Reflect the filters in the URL so a view can be bookmarked/shared.
  useEffect(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (type) p.set("type", type);
    if (email) p.set("email", email);
    if (page > 1) p.set("page", String(page));
    const qs = p.toString();
    router.replace(qs ? `/admin/jobs?${qs}` : "/admin/jobs", { scroll: false });
  }, [status, type, email, page, router]);

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
      <PageHeader
        title="Jobs"
        description="Every generation job, newest first"
        actions={
          <>
            <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={auto}
                onChange={(e) => setAuto(e.target.checked)}
              />
              Auto-refresh
            </label>
            <Button variant="secondary" onClick={reload} disabled={loading}>
              Refresh
            </Button>
          </>
        }
      />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="User email" htmlFor="job-email" className="w-full sm:w-56">
          <Input
            id="job-email"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="search by email…"
          />
        </Field>
        <Field label="Status" htmlFor="job-status">
          <Select
            id="job-status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="pending">pending</option>
            <option value="running">running</option>
            <option value="streaming">streaming</option>
            <option value="complete">complete</option>
            <option value="error">error</option>
          </Select>
        </Field>
        <Field label="Type" htmlFor="job-type" className="w-full sm:w-44">
          <Input
            id="job-type"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setPage(1);
            }}
            placeholder="music, lyrics, stems…"
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
          title="No jobs found."
          description={total ? "No rows match your filters." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Created</th>
                <th scope="col" className="px-4 py-3">Type</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3" title="Customer who submitted the job">
                  User
                </th>
                <th scope="col" className="px-4 py-3">Model</th>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
                <th
                  scope="col"
                  className="px-4 py-3"
                  title="Pooled Suno login that ran the job — not the customer"
                >
                  Suno account
                </th>
                <th scope="col" className="px-4 py-3">Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((j) => (
                <tr key={j.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(j.created_at)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{j.type}</td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONES[j.status] ?? "neutral"}>{j.status}</Badge>
                  </td>
                  <td className="px-4 py-3">{j.email ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">{j.model ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(j.credits)}</td>
                  <td
                    className="px-4 py-3 text-xs text-[var(--muted)]"
                    title="Pooled Suno login that ran the job — not the customer"
                  >
                    {j.account_id ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {j.error ? (
                      <span
                        className="block max-w-xs truncate text-xs text-red-300"
                        title={j.error}
                      >
                        {j.error}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
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

export default function JobsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <JobsInner />
    </Suspense>
  );
}
