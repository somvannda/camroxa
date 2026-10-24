"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { dateTime, num } from "@/lib/format";

type InviteStatus = "pending" | "rewarded" | "skipped" | "rejected";
type RewardMode = "percent" | "fixed";

interface RewardRule {
  mode: RewardMode;
  value: number;
}

interface InviteSettings {
  enabled: boolean;
  inviter: RewardRule;
  invitee: RewardRule;
}

interface InviteRow {
  id: string;
  status: InviteStatus;
  code: string;
  invitee_email: string;
  invited_ip: string | null;
  purchased_credits: number | null;
  inviter_reward: number;
  invitee_reward: number;
  qualifying_transaction_id: string | null;
  created_at: string;
  rewarded_at: string | null;
  inviter_id: string;
  inviter_email: string;
  inviter_name: string | null;
}

interface InvitesResponse {
  rows: InviteRow[];
  total: number;
  page: number;
  page_size: number;
  settings: InviteSettings;
  summary: {
    total: number;
    pending: number;
    rewarded: number;
    skipped: number;
    rejected: number;
    inviter_credits: number;
    invitee_credits: number;
  };
}

const PAGE_SIZE = 25;

const STATUS_TONE: Record<InviteStatus, BadgeTone> = {
  pending: "warning",
  rewarded: "success",
  skipped: "neutral",
  rejected: "danger",
};

function rewardRuleText(rule: RewardRule): string {
  return rule.mode === "percent"
    ? `${rule.value}% of the purchased credits`
    : `${num(rule.value)} credits`;
}

export default function InvitesPage() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");

  const { data, loading, error, reload, setData } = useResource<InvitesResponse>(() => {
    const p = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (statusFilter) p.set("status", statusFilter);
    return apiFetch<InvitesResponse>(`/admin/invites?${p.toString()}`);
  }, [page, q, statusFilter]);

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const summary = data?.summary;

  // The form starts as `null` and falls back to the server's settings, so
  // loading data never requires a setState-in-effect round trip. Saving writes
  // the fresh server value back into `form`.
  const [form, setForm] = useState<InviteSettings | null>(null);
  const settings = form ?? data?.settings ?? null;
  const [savingSettings, setSavingSettings] = useState(false);

  const [pendingReject, setPendingReject] = useState<InviteRow | null>(null);
  const [pendingRestore, setPendingRestore] = useState<InviteRow | null>(null);

  function patchRule(side: "inviter" | "invitee", patch: Partial<RewardRule>) {
    const current = settings ?? {
      enabled: true,
      inviter: { mode: "percent" as RewardMode, value: 15 },
      invitee: { mode: "percent" as RewardMode, value: 15 },
    };
    const nextRule = { ...current[side], ...patch };
    // Keep the form valid while switching modes: a fixed amount above 100 is
    // not a legal percentage, so clamp it instead of failing on save.
    if (nextRule.mode === "percent" && nextRule.value > 100) nextRule.value = 100;
    setForm({ ...current, [side]: nextRule });
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSavingSettings(true);
    try {
      const saved = await apiFetch<InviteSettings>("/admin/invites/settings", {
        method: "PUT",
        body: JSON.stringify({ settings }),
      });
      setForm(saved);
      setData((prev) => (prev ? { ...prev, settings: saved } : prev));
      toast.success("Invite program settings saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save invite settings");
    } finally {
      setSavingSettings(false);
    }
  }

  async function reject(row: InviteRow) {
    try {
      await apiFetch(`/admin/invites/${row.id}/reject`, { method: "POST" });
      toast.success("Invite rejected.");
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reject invite");
    }
  }

  async function restore(row: InviteRow) {
    try {
      await apiFetch(`/admin/invites/${row.id}/restore`, { method: "POST" });
      toast.success("Invite restored.");
      void reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to restore invite");
    }
  }

  function applySearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setQ(qInput.trim());
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Invite Program"
        description="Reward users for bringing friends who buy their first credit pack"
      />

      {error && <ErrorState message={error} onRetry={() => void reload()} />}

      {settings && (
        <Card className="space-y-5 p-5">
          <form onSubmit={saveSettings} className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-[var(--muted)]">Program settings</h2>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  Rewards are paid once per invited friend, only after their first paid credit pack.
                </p>
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={settings.enabled}
                  onChange={(e) => setForm({ ...settings, enabled: e.target.checked })}
                />
                Program enabled
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-[var(--border)] bg-black/20 p-4">
                <div className="mb-3 text-sm font-medium">Inviter earns</div>
                <div className="grid grid-cols-[130px_1fr] gap-3">
                  <Field label="Reward type" htmlFor="inviter-mode">
                    <Select
                      id="inviter-mode"
                      value={settings.inviter.mode}
                      onChange={(e) =>
                        patchRule("inviter", { mode: e.target.value as RewardMode })
                      }
                    >
                      <option value="percent">Percent</option>
                      <option value="fixed">Fixed credits</option>
                    </Select>
                  </Field>
                  <Field
                    label={settings.inviter.mode === "percent" ? "Percent" : "Credits"}
                    htmlFor="inviter-value"
                    hint={rewardRuleText(settings.inviter)}
                  >
                    <Input
                      id="inviter-value"
                      type="number"
                      min="0"
                      max={settings.inviter.mode === "percent" ? 100 : 1_000_000}
                      step="1"
                      value={settings.inviter.value}
                      onChange={(e) =>
                        patchRule("inviter", { value: Number(e.target.value) })
                      }
                    />
                  </Field>
                </div>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-black/20 p-4">
                <div className="mb-3 text-sm font-medium">Invitee receives</div>
                <div className="grid grid-cols-[130px_1fr] gap-3">
                  <Field label="Reward type" htmlFor="invitee-mode">
                    <Select
                      id="invitee-mode"
                      value={settings.invitee.mode}
                      onChange={(e) =>
                        patchRule("invitee", { mode: e.target.value as RewardMode })
                      }
                    >
                      <option value="percent">Percent</option>
                      <option value="fixed">Fixed credits</option>
                    </Select>
                  </Field>
                  <Field
                    label={settings.invitee.mode === "percent" ? "Percent" : "Credits"}
                    htmlFor="invitee-value"
                    hint={rewardRuleText(settings.invitee)}
                  >
                    <Input
                      id="invitee-value"
                      type="number"
                      min="0"
                      max={settings.invitee.mode === "percent" ? 100 : 1_000_000}
                      step="1"
                      value={settings.invitee.value}
                      onChange={(e) =>
                        patchRule("invitee", { value: Number(e.target.value) })
                      }
                    />
                  </Field>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={savingSettings}>
                {savingSettings ? "Saving…" : "Save settings"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {summary && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Invites"
            value={num(summary.total)}
            hint={`${num(summary.pending)} awaiting first purchase`}
          />
          <StatCard label="Rewarded" value={num(summary.rewarded)} hint="Paid once per friend" />
          <StatCard
            label="Inviter credits"
            value={num(summary.inviter_credits)}
            hint="Total paid to inviters"
          />
          <StatCard
            label="Invitee credits"
            value={num(summary.invitee_credits)}
            hint={`${num(summary.skipped)} skipped · ${num(summary.rejected)} rejected`}
          />
        </div>
      )}

      <Card className="p-4">
        <form onSubmit={applySearch} className="flex flex-wrap items-end gap-3">
          <Field label="Search" htmlFor="invite-search" className="min-w-[220px] flex-1">
            <Input
              id="invite-search"
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
              placeholder="Inviter or invitee email, code…"
            />
          </Field>
          <Field label="Status" htmlFor="invite-status">
            <Select
              id="invite-status"
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value);
              }}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="rewarded">Rewarded</option>
              <option value="skipped">Skipped</option>
              <option value="rejected">Rejected</option>
            </Select>
          </Field>
          <Button type="submit" variant="secondary">
            Search
          </Button>
          {(q || statusFilter) && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setQInput("");
                setQ("");
                setStatusFilter("");
                setPage(1);
              }}
            >
              Clear
            </Button>
          )}
        </form>
      </Card>

      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No invites yet."
          description="Invite links are captured when a new user signs up through a friend's link."
        />
      ) : (
        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-left text-xs text-[var(--muted)]">
              <tr>
                <th scope="col" className="px-4 py-3">Inviter</th>
                <th scope="col" className="px-4 py-3">Invitee</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Purchase</th>
                <th scope="col" className="px-4 py-3 text-right">Rewards</th>
                <th scope="col" className="px-4 py-3">IP</th>
                <th scope="col" className="px-4 py-3">Created</th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-[var(--border)]">
                  <td className="px-4 py-3">
                    <div className="font-medium">{row.inviter_email}</div>
                    {row.inviter_name && (
                      <div className="text-xs text-[var(--muted)]">{row.inviter_name}</div>
                    )}
                    <div className="font-mono text-[11px] text-[var(--muted)]">{row.code}</div>
                  </td>
                  <td className="px-4 py-3">{row.invitee_email}</td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[row.status]}>{row.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {row.purchased_credits != null ? num(row.purchased_credits) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-xs">
                    {row.status === "rewarded" ? (
                      <span className="whitespace-nowrap text-[var(--muted)]">
                        {num(row.inviter_reward)} / {num(row.invitee_reward)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">
                    {row.invited_ip ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">
                    {dateTime(row.created_at)}
                    {row.rewarded_at && (
                      <div>rewarded {dateTime(row.rewarded_at)}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.status === "pending" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-300"
                        onClick={() => setPendingReject(row)}
                      >
                        Reject
                      </Button>
                    )}
                    {(row.status === "rejected" || row.status === "skipped") && (
                      <Button size="sm" variant="ghost" onClick={() => setPendingRestore(row)}>
                        Restore
                      </Button>
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
        open={!!pendingReject}
        title="Reject invite"
        danger
        confirmLabel="Reject"
        message={
          pendingReject
            ? `Reject the invite from ${pendingReject.inviter_email} to ${pendingReject.invitee_email}? It will no longer qualify for a reward.`
            : ""
        }
        onConfirm={() => (pendingReject ? reject(pendingReject) : Promise.resolve())}
        onClose={() => setPendingReject(null)}
      />

      <ConfirmDialog
        open={!!pendingRestore}
        title="Restore invite"
        confirmLabel="Restore"
        message={
          pendingRestore
            ? `Restore the invite from ${pendingRestore.inviter_email} to ${pendingRestore.invitee_email}? Their next paid credit-pack purchase will qualify.`
            : ""
        }
        onConfirm={() => (pendingRestore ? restore(pendingRestore) : Promise.resolve())}
        onClose={() => setPendingRestore(null)}
      />
    </div>
  );
}
