"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

interface PaymentRow {
  id: string;
  email: string;
  provider: string;
  credit_amount: number;
  currency: string;
  amount: string | number;
  payment_method: string;
  status: string;
  provider_payment_id: string | null;
  gateway_payment_id: string | null;
  bill_number: string | null;
  error_message: string | null;
  paid_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface PaymentPage {
  rows: PaymentRow[];
  total: number;
  page: number;
  page_size: number;
}

const STATUS_TONES: Record<string, BadgeTone> = {
  paid: "success",
  pending: "warning",
  expired: "neutral",
  failed: "danger",
  refunded: "info",
};

const PAGE_SIZE = 25;

function money(amount: string | number, currency: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `— ${currency}`;
  return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export default function PaymentsPage() {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [email, setEmail] = useState("");
  const [page, setPage] = useState(1);
  const [pendingRefund, setPendingRefund] = useState<PaymentRow | null>(null);

  const { data, loading, error, reload } = useResource<PaymentPage>(
    () => {
      const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
      if (status) p.set("status", status);
      if (email) p.set("email", email);
      return apiFetch<PaymentPage>(`/admin/payments?${p.toString()}`);
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

  async function refund(r: PaymentRow) {
    try {
      await apiFetch(`/admin/payments/${r.id}/refund`, { method: "POST" });
      toast.success(
        `Refunded ${money(r.amount, r.currency)} and clawed back ${num(r.credit_amount)} credits.`,
      );
      void reload();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to refund payment");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payments"
        description="Credit-pack purchases and their provider status"
      />

      <form onSubmit={applySearch} className="flex flex-wrap items-end gap-2">
        <Field label="User email" htmlFor="pay-email" className="w-full sm:w-64">
          <Input
            id="pay-email"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="search by email…"
          />
        </Field>
        <Field label="Status" htmlFor="pay-status">
          <Select
            id="pay-status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="pending">pending</option>
            <option value="paid">paid</option>
            <option value="expired">expired</option>
            <option value="failed">failed</option>
            <option value="refunded">refunded</option>
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
          title="No payments found."
          description={total ? "No rows match your filters." : undefined}
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Created</th>
                <th scope="col" className="px-4 py-3">User</th>
                <th scope="col" className="px-4 py-3 text-right">Credits</th>
                <th scope="col" className="px-4 py-3 text-right">Amount</th>
                <th scope="col" className="px-4 py-3">Provider</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3">Paid</th>
                <th scope="col" className="px-4 py-3">Reference</th>
                <th scope="col" className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(r.created_at)}
                  </td>
                  <td className="px-4 py-3">{r.email}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{num(r.credit_amount)}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap tabular-nums">
                    {money(r.amount, r.currency)}
                  </td>
                  <td className="px-4 py-3 capitalize text-[var(--muted)]">{r.provider}</td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONES[r.status] ?? "neutral"}>{r.status}</Badge>
                    {r.error_message && (
                      <div
                        className="mt-1 max-w-[16rem] truncate text-[11px] text-red-300"
                        title={r.error_message}
                      >
                        {r.error_message}
                      </div>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--muted)]">
                    {r.paid_at ? dateTime(r.paid_at) : "—"}
                  </td>
                  <td
                    className="px-4 py-3 font-mono text-[11px] text-[var(--muted)]"
                    title={r.provider_payment_id ?? r.gateway_payment_id ?? r.bill_number ?? ""}
                  >
                    {r.provider_payment_id ?? r.gateway_payment_id ?? r.bill_number ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {r.provider === "chmaba" && r.status === "paid" ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-300"
                        onClick={() => setPendingRefund(r)}
                      >
                        Refund
                      </Button>
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

      <ConfirmDialog
        open={!!pendingRefund}
        title="Refund payment"
        danger
        confirmLabel="Refund"
        message={
          pendingRefund
            ? `Refund ${money(pendingRefund.amount, pendingRefund.currency)} and claw back ${num(
                pendingRefund.credit_amount,
              )} credits from ${pendingRefund.email}? This cannot be undone.`
            : ""
        }
        onConfirm={() => (pendingRefund ? refund(pendingRefund) : Promise.resolve())}
        onClose={() => setPendingRefund(null)}
      />
    </div>
  );
}
