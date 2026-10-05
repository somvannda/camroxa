"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

interface LedgerRow {
  id: string;
  email: string;
  amount: number;
  type: string;
  description: string | null;
  job_id: string | null;
  created_at: string;
}

interface LedgerPage {
  rows: LedgerRow[];
  total: number;
  page: number;
  page_size: number;
}

const TYPE_TONES: Record<string, BadgeTone> = {
  purchase: "success",
  adjust: "warning",
  spend: "neutral",
  refund: "info",
};

const PAGE_SIZE = 25;

export default function TransactionsPage() {
  const toast = useToast();
  const [type, setType] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [email, setEmail] = useState("");
  const [page, setPage] = useState(1);

  const { data, loading, error, reload } = useResource<LedgerPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (type) p.set("type", type);
      if (email) p.set("email", email);
      return apiFetch<LedgerPage>(`/admin/transactions?${p.toString()}`);
    },
    [page, type, email],
  );

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setEmail(emailInput.trim());
  }

  async function exportCsv() {
    const p = new URLSearchParams({ format: "csv" });
    if (type) p.set("type", type);
    if (email) p.set("email", email);
    try {
      const res = await fetch(`/backend/admin/transactions?${p.toString()}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "credit-ledger.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Credit Ledger"
        description="Every credit movement — purchases, adjustments, spend and refunds"
        actions={
          <Button variant="secondary" onClick={exportCsv}>
            Export CSV
          </Button>
        }
      />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="User email" htmlFor="ledger-email" className="w-full sm:w-64">
          <Input
            id="ledger-email"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="search by email…"
          />
        </Field>
        <Field label="Type" htmlFor="ledger-type">
          <Select
            id="ledger-type"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="purchase">purchase</option>
            <option value="adjust">adjust</option>
            <option value="spend">spend</option>
            <option value="refund">refund</option>
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
          title="No ledger entries found."
          description={total ? "No rows match your filters." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Time</th>
                <th scope="col" className="px-4 py-3">User</th>
                <th scope="col" className="px-4 py-3">Type</th>
                <th scope="col" className="px-4 py-3 text-right">Amount</th>
                <th scope="col" className="px-4 py-3">Description</th>
                <th scope="col" className="px-4 py-3">Job</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(r.created_at)}
                  </td>
                  <td className="px-4 py-3">{r.email}</td>
                  <td className="px-4 py-3">
                    <Badge tone={TYPE_TONES[r.type] ?? "neutral"}>{r.type}</Badge>
                  </td>
                  <td
                    className={`px-4 py-3 text-right tabular-nums ${
                      r.amount > 0 ? "text-emerald-300" : r.amount < 0 ? "text-red-300" : ""
                    }`}
                  >
                    {r.amount > 0 ? "+" : ""}
                    {num(r.amount)}
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{r.description ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-[var(--muted)]">
                    {r.job_id ? r.job_id.slice(0, 8) : "—"}
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
