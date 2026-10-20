import { useMemo, useState } from 'react';
import { Gift, RefreshCcw, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { LoadingSkeleton } from '@/components/shared/loading-skeleton';
import { PageHeader } from '@/components/shared/page-header';
import { toast } from '@/hooks/use-toast';
import {
  useInviteProgram,
  useRejectInvite,
  useRestoreInvite,
  useUpdateInviteSettings,
} from '@/hooks/use-invite-program';
import type {
  InviteProgramRow,
  InviteProgramSettings,
  InviteProgramStatus,
  InviteRewardMode,
} from '@/types/models';

const PAGE_SIZE = 25;

const STATUS_CLASS: Record<InviteProgramStatus, string> = {
  pending: 'border-amber-400/25 bg-amber-500/10 text-amber-300',
  rewarded: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300',
  skipped: 'border-white/10 bg-white/[0.04] text-slate-400',
  rejected: 'border-rose-400/25 bg-rose-500/10 text-rose-300',
};

function rewardRuleText(mode: InviteRewardMode, value: number): string {
  return mode === 'percent'
    ? `${value}% of the purchased credits`
    : `${value.toLocaleString()} credits`;
}

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export default function InviteProgramPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<InviteProgramStatus | ''>('');
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');

  const params = useMemo(
    () => ({ page, pageSize: PAGE_SIZE, status, q: query }),
    [page, status, query],
  );
  const queryResult = useInviteProgram(params);
  const data = queryResult.data;
  const updateSettings = useUpdateInviteSettings();
  const rejectInvite = useRejectInvite();
  const restoreInvite = useRestoreInvite();

  const [form, setForm] = useState<InviteProgramSettings | null>(null);
  const settings = form ?? data?.settings ?? null;
  const [rejectTarget, setRejectTarget] = useState<InviteProgramRow | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<InviteProgramRow | null>(null);

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function patchRule(side: 'inviter' | 'invitee', patch: { mode?: InviteRewardMode; value?: number }) {
    const current = settings;
    if (!current) return;
    const nextRule = { ...current[side], ...patch };
    if (nextRule.mode === 'percent' && nextRule.value > 100) nextRule.value = 100;
    setForm({ ...current, [side]: nextRule });
  }

  function saveSettings(event: React.FormEvent) {
    event.preventDefault();
    if (!settings) return;
    updateSettings.mutate(settings, {
      onSuccess: (saved) => {
        setForm(saved);
        toast({ title: 'Invite program settings saved.' });
      },
      onError: (error) => {
        toast({
          title: 'Could not save settings',
          description: error instanceof Error ? error.message : undefined,
          variant: 'destructive',
        });
      },
    });
  }

  function applySearch(event: React.FormEvent) {
    event.preventDefault();
    setPage(1);
    setQuery(searchInput.trim());
  }

  function confirmReject() {
    if (!rejectTarget) return;
    rejectInvite.mutate(rejectTarget.id, {
      onSuccess: () => {
        toast({ title: 'Referral rejected.' });
        setRejectTarget(null);
      },
      onError: (error) => {
        toast({
          title: 'Could not reject referral',
          description: error instanceof Error ? error.message : undefined,
          variant: 'destructive',
        });
      },
    });
  }

  function confirmRestore() {
    if (!restoreTarget) return;
    restoreInvite.mutate(restoreTarget.id, {
      onSuccess: () => {
        toast({ title: 'Referral restored.' });
        setRestoreTarget(null);
      },
      onError: (error) => {
        toast({
          title: 'Could not restore referral',
          description: error instanceof Error ? error.message : undefined,
          variant: 'destructive',
        });
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Accounts"
        title="Invite Program"
        description="Reward users for bringing friends who buy their first credit pack on music.camxora.com."
      />

      {queryResult.isError ? (
        <ErrorState
          message={
            queryResult.error instanceof Error
              ? queryResult.error.message
              : 'Could not load the invite program. Please try again.'
          }
          onRetry={() => void queryResult.refetch()}
        />
      ) : null}

      {settings ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gift className="h-4 w-4 text-violet-300" /> Program settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={saveSettings} className="space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/40 p-4">
                <div>
                  <div className="text-sm font-medium text-white">Program enabled</div>
                  <p className="text-xs text-slate-400">
                    Rewards are paid once per invited friend, only after their first paid credit pack.
                  </p>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-200">
                  <input
                    type="checkbox"
                    checked={settings.enabled}
                    onChange={(event) => setForm({ ...settings, enabled: event.target.checked })}
                    className="h-4 w-4 accent-violet-500"
                  />
                  Enabled
                </label>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                {(['inviter', 'invitee'] as const).map((side) => (
                  <div key={side} className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
                    <div className="mb-3 text-sm font-medium text-white">
                      {side === 'inviter' ? 'Inviter earns' : 'Invitee receives'}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-[150px_1fr]">
                      <div className="space-y-1">
                        <Label htmlFor={`${side}-mode`}>Reward type</Label>
                        <Select
                          value={settings[side].mode}
                          onValueChange={(value) =>
                            patchRule(side, { mode: value as InviteRewardMode })
                          }
                        >
                          <SelectTrigger id={`${side}-mode`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="percent">Percent</SelectItem>
                            <SelectItem value="fixed">Fixed credits</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`${side}-value`}>
                          {settings[side].mode === 'percent' ? 'Percent' : 'Credits'}
                        </Label>
                        <Input
                          id={`${side}-value`}
                          type="number"
                          min={0}
                          max={settings[side].mode === 'percent' ? 100 : 1_000_000}
                          step={1}
                          value={settings[side].value}
                          onChange={(event) =>
                            patchRule(side, { value: Number(event.target.value) })
                          }
                        />
                        <p className="text-[11px] text-slate-500">
                          {rewardRuleText(settings[side].mode, settings[side].value)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={updateSettings.isPending}>
                  {updateSettings.isPending ? 'Saving…' : 'Save settings'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {data ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: 'Invites',
              value: data.summary.total,
              hint: `${data.summary.pending.toLocaleString()} awaiting first purchase`,
            },
            {
              label: 'Rewarded',
              value: data.summary.rewarded,
              hint: 'Paid once per friend',
            },
            {
              label: 'Inviter credits',
              value: data.summary.inviter_credits,
              hint: 'Total paid to inviters',
            },
            {
              label: 'Invitee credits',
              value: data.summary.invitee_credits,
              hint: `${data.summary.skipped.toLocaleString()} skipped · ${data.summary.rejected.toLocaleString()} rejected`,
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-xl border border-white/10 bg-slate-950/50 p-4"
            >
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{stat.label}</div>
              <div className="mt-1 text-2xl font-semibold text-white tabular-nums">
                {stat.value.toLocaleString()}
              </div>
              <div className="mt-1 text-xs text-slate-500">{stat.hint}</div>
            </div>
          ))}
        </div>
      ) : null}

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={applySearch} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[220px] flex-1 space-y-1">
              <Label htmlFor="invite-search">Search</Label>
              <Input
                id="invite-search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Inviter or invitee email, code…"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="invite-status">Status</Label>
              <Select
                value={status || 'all'}
                onValueChange={(value) => {
                  setPage(1);
                  setStatus(value === 'all' ? '' : (value as InviteProgramStatus));
                }}
              >
                <SelectTrigger id="invite-status" className="w-[170px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="rewarded">Rewarded</SelectItem>
                  <SelectItem value="skipped">Skipped</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" variant="secondary">
              <Search className="mr-2 h-4 w-4" /> Search
            </Button>
            {(query || status) && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSearchInput('');
                  setQuery('');
                  setStatus('');
                  setPage(1);
                }}
              >
                Clear
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              onClick={() => void queryResult.refetch()}
              disabled={queryResult.isFetching}
            >
              <RefreshCcw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </form>
        </CardContent>
      </Card>

      {queryResult.isLoading ? (
        <LoadingSkeleton />
      ) : !data || data.rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-slate-400">
            No referrals yet. Invite links are captured when a new user signs up through a friend's
            link.
          </CardContent>
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/50">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.03] text-left text-xs uppercase tracking-[0.12em] text-slate-500">
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
              {data.rows.map((row) => (
                <tr key={row.id} className="border-t border-white/5">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{row.inviter_email}</div>
                    {row.inviter_name ? (
                      <div className="text-xs text-slate-500">{row.inviter_name}</div>
                    ) : null}
                    <div className="font-mono text-[11px] text-slate-500">{row.code}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-300">{row.invitee_email}</td>
                  <td className="px-4 py-3">
                    <Badge className={STATUS_CLASS[row.status]}>{row.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-300">
                    {row.purchased_credits != null ? row.purchased_credits.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-slate-400">
                    {row.status === 'rewarded'
                      ? `${row.inviter_reward.toLocaleString()} / ${row.invitee_reward.toLocaleString()}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {row.invited_ip ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {formatDate(row.created_at)}
                    {row.rewarded_at ? (
                      <div>rewarded {formatDate(row.rewarded_at)}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.status === 'pending' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-rose-300"
                        onClick={() => setRejectTarget(row)}
                      >
                        Reject
                      </Button>
                    ) : null}
                    {row.status === 'rejected' || row.status === 'skipped' ? (
                      <Button size="sm" variant="ghost" onClick={() => setRestoreTarget(row)}>
                        Restore
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE_SIZE ? (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>{total.toLocaleString()} total</span>
          <span className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              Previous
            </Button>
            <span>
              Page {page} / {pages}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= pages}
              onClick={() => setPage((value) => Math.min(pages, value + 1))}
            >
              Next
            </Button>
          </span>
        </div>
      ) : null}

      <ConfirmDialog
        open={!!rejectTarget}
        onOpenChange={(open) => {
          if (!open) setRejectTarget(null);
        }}
        title="Reject referral"
        description={
          rejectTarget
            ? `Reject the referral from ${rejectTarget.inviter_email} to ${rejectTarget.invitee_email}? It will no longer qualify for a reward.`
            : ''
        }
        confirmText="Reject"
        variant="destructive"
        isLoading={rejectInvite.isPending}
        onConfirm={confirmReject}
      />

      <ConfirmDialog
        open={!!restoreTarget}
        onOpenChange={(open) => {
          if (!open) setRestoreTarget(null);
        }}
        title="Restore referral"
        description={
          restoreTarget
            ? `Restore the referral from ${restoreTarget.inviter_email} to ${restoreTarget.invitee_email}? Their next paid credit-pack purchase will qualify.`
            : ''
        }
        confirmText="Restore"
        isLoading={restoreInvite.isPending}
        onConfirm={confirmRestore}
      />
    </div>
  );
}
