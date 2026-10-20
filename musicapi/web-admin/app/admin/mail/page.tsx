"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

interface MailHealth {
  configured: boolean;
  enabled: boolean;
  baseUrl: string;
  fromTransactional: string;
  fromCampaign: string;
  queueDepth: number;
  counts: Record<string, number>;
}

interface DeliveryRow {
  id: string;
  email: string;
  kind: string;
  subject: string;
  status: string;
  open_count: number;
  click_count: number;
  sent_at: string | null;
  delivered_at: string | null;
  first_opened_at: string | null;
  first_clicked_at: string | null;
  error: string | null;
  created_at: string;
}

interface DeliveriesResponse {
  rows: DeliveryRow[];
  stats: { total: number; delivered: number; opened: number; clicked: number; bounced: number };
  suppressed: number;
}

interface SuppressionsResponse {
  rows: Array<{ email: string; reason: string; source: string | null; created_at: string }>;
}

const STATUSES = [
  "queued",
  "sending",
  "sent",
  "delivered",
  "opened",
  "clicked",
  "bounced",
  "complained",
  "failed",
  "suppressed",
  "skipped",
];

const STATUS_STYLE: Record<string, string> = {
  delivered: "bg-emerald-500/15 text-emerald-300",
  opened: "bg-sky-500/15 text-sky-300",
  clicked: "bg-violet-500/15 text-violet-300",
  sent: "bg-white/10 text-white",
  queued: "bg-amber-500/15 text-amber-300",
  sending: "bg-amber-500/15 text-amber-300",
  bounced: "bg-red-500/15 text-red-300",
  complained: "bg-red-500/15 text-red-300",
  failed: "bg-red-500/15 text-red-300",
  suppressed: "bg-white/10 text-[var(--muted)]",
  skipped: "bg-white/10 text-[var(--muted)]",
};

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_STYLE[status] ?? "bg-white/10"}`}>
      {status}
    </span>
  );
}

export default function MailPage() {
  const toast = useToast();
  const [status, setStatus] = useState("");

  const health = useResource<MailHealth>(() => apiFetch<MailHealth>("/admin/mail/health"));
  const deliveries = useResource<DeliveriesResponse>(() =>
    apiFetch<DeliveriesResponse>(`/admin/mail/deliveries?limit=100${status ? `&status=${status}` : ""}`),
  );
  const suppressions = useResource<SuppressionsResponse>(() =>
    apiFetch<SuppressionsResponse>("/admin/mail/suppressions"),
  );

  const [testTo, setTestTo] = useState("");
  const [testSubject, setTestSubject] = useState("CAMXORA mail test");
  const [sending, setSending] = useState(false);
  const [draining, setDraining] = useState(false);

  const stats = deliveries.data?.stats;

  async function sendTest(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    try {
      const res = await apiFetch<{ to: string }>("/admin/mail/test", {
        method: "POST",
        body: JSON.stringify({ to: testTo || undefined, subject: testSubject }),
      });
      toast.success(`Test mail accepted for ${res.to}.`);
      void deliveries.reload();
      void health.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test send failed");
    } finally {
      setSending(false);
    }
  }

  async function drainQueue() {
    setDraining(true);
    try {
      const res = await apiFetch<{ sent: number }>("/admin/mail/process", {
        method: "POST",
        body: "{}",
      });
      toast.success(`Delivered ${res.sent} queued message(s).`);
      void deliveries.reload();
      void health.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Queue drain failed");
    } finally {
      setDraining(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mail"
        description="Delivery ledger, engagement tracking and suppression list for music.camxora.com"
        actions={
          <>
            <Button variant="secondary" onClick={() => void drainQueue()} disabled={draining}>
              {draining ? "Draining..." : "Drain queue"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                void health.reload();
                void deliveries.reload();
                void suppressions.reload();
              }}
            >
              Refresh
            </Button>
          </>
        }
      />

      {health.error && <ErrorState message={health.error} onRetry={health.reload} />}
      {health.loading && <LoadingState />}

      {health.data && (
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  health.data.configured && health.data.enabled ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              <span className="font-semibold">
                {health.data.configured && health.data.enabled
                  ? "Resend connected"
                  : health.data.configured
                    ? "Sending paused"
                    : "API key not configured"}
              </span>
            </div>
            <span className="text-xs text-[var(--muted)]">{health.data.queueDepth} queued</span>
          </div>

          <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-[var(--muted)]">Transactional From</dt>
              <dd className="break-all">{health.data.fromTransactional}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Marketing From</dt>
              <dd className="break-all">{health.data.fromCampaign}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-[var(--muted)]">Tracking / unsubscribe base</dt>
              <dd className="break-all">{health.data.baseUrl}</dd>
            </div>
          </dl>

          {!health.data.configured && (
            <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              Add a Resend API key in Settings &gt; Mail (Resend). Sending stays disabled until then;
              the ledger and this page keep working.
            </p>
          )}
        </Card>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            { label: "Total", value: stats.total },
            { label: "Delivered", value: stats.delivered },
            { label: "Opened", value: stats.opened },
            { label: "Clicked", value: stats.clicked },
            { label: "Bounced", value: stats.bounced },
          ].map((item) => (
            <Card key={item.label} className="p-4">
              <p className="text-xs text-[var(--muted)]">{item.label}</p>
              <p className="text-xl font-bold">{num(item.value)}</p>
            </Card>
          ))}
        </div>
      )}

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">Send a test</h2>
        <form onSubmit={sendTest} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label="To" hint="Leave blank to send to your own admin address.">
            <Input
              type="email"
              placeholder="you@camxora.com"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
            />
          </Field>
          <Field label="Subject">
            <Input value={testSubject} onChange={(e) => setTestSubject(e.target.value)} />
          </Field>
          <Button type="submit" disabled={sending}>
            {sending ? "Sending..." : "Send test"}
          </Button>
        </form>
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Deliveries</h2>
          <Field className="w-44">
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {deliveries.error && <ErrorState message={deliveries.error} onRetry={deliveries.reload} />}
        {deliveries.loading && <LoadingState />}

        {deliveries.data && deliveries.data.rows.length === 0 && (
          <EmptyState
            title="No mail yet"
            description="Send a test message above. Every delivery is recorded here with its open and click counts."
          />
        )}

        {deliveries.data && deliveries.data.rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-[var(--muted)]">
                <tr>
                  <th className="py-2 pr-3 font-medium">Recipient</th>
                  <th className="py-2 pr-3 font-medium">Subject</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 text-right font-medium">Opens</th>
                  <th className="py-2 pr-3 text-right font-medium">Clicks</th>
                  <th className="py-2 pr-3 font-medium">Sent</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.data.rows.map((row) => (
                  <tr key={row.id} className="border-t border-[var(--border)]">
                    <td className="py-2 pr-3">
                      <span className="break-all">{row.email}</span>
                      <span className="ml-2 text-[11px] text-[var(--muted)]">{row.kind}</span>
                    </td>
                    <td className="max-w-[22rem] truncate py-2 pr-3" title={row.subject}>
                      {row.subject}
                    </td>
                    <td className="py-2 pr-3">
                      <StatusPill status={row.status} />
                      {row.error && (
                        <span className="ml-2 text-[11px] text-red-300" title={row.error}>
                          {row.error.slice(0, 40)}
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-right">{num(row.open_count)}</td>
                    <td className="py-2 pr-3 text-right">{num(row.click_count)}</td>
                    <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--muted)]">
                      {dateTime(row.sent_at ?? row.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="mb-1 font-semibold">Suppression list</h2>
        <p className="mb-3 text-xs text-[var(--muted)]">
          Hard stops. These addresses never receive mail, not even receipts, until removed.
        </p>

        {suppressions.error && (
          <ErrorState message={suppressions.error} onRetry={suppressions.reload} />
        )}

        {suppressions.data && suppressions.data.rows.length === 0 && (
          <p className="text-sm text-[var(--muted)]">
            Nothing suppressed. Bounces and complaints are added automatically by the Resend webhook.
          </p>
        )}

        {suppressions.data && suppressions.data.rows.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-3 font-medium">Email</th>
                <th className="py-2 pr-3 font-medium">Reason</th>
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 font-medium">Added</th>
              </tr>
            </thead>
            <tbody>
              {suppressions.data.rows.map((row) => (
                <tr key={row.email} className="border-t border-[var(--border)]">
                  <td className="break-all py-2 pr-3">{row.email}</td>
                  <td className="py-2 pr-3">{row.reason}</td>
                  <td className="py-2 pr-3 text-[var(--muted)]">{row.source ?? "-"}</td>
                  <td className="py-2 pr-3 text-xs text-[var(--muted)]">{dateTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
