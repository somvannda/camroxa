'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Check, Copy, Gift, LoaderCircle, Sparkles, UserPlus } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import {
  fetchInviteProgram,
  type InviteProgram,
  type InviteRewardRule,
} from '@/lib/invite-api';

function rewardText(rule: InviteRewardRule): string {
  if (rule.value <= 0) return 'No reward';
  return rule.mode === 'percent'
    ? `${rule.value}% of their purchase credits`
    : `${rule.value.toLocaleString()} credits`;
}

function statusChip(status: string): { label: string; className: string } {
  switch (status) {
    case 'rewarded':
      return {
        label: 'Rewarded',
        className: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300',
      };
    case 'rejected':
      return {
        label: 'Rejected',
        className: 'border-rose-400/25 bg-rose-500/10 text-rose-300',
      };
    case 'skipped':
      return {
        label: 'Skipped',
        className: 'border-white/10 bg-white/[0.04] text-slate-400',
      };
    default:
      return {
        label: 'Waiting for first purchase',
        className: 'border-amber-400/25 bg-amber-500/10 text-amber-300',
      };
  }
}

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString();
}

export default function InvitePage() {
  const { user, loading } = useAuth();
  const [data, setData] = useState<InviteProgram | null>(null);
  const [shareUrl, setShareUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<'link' | 'code' | null>(null);

  useEffect(() => {
    if (!user) return;
    let active = true;
    fetchInviteProgram()
      .then((program) => {
        if (!active) return;
        setData(program);
        setShareUrl(`${window.location.origin}${program.share_path}`);
        setError(null);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load the invite program');
      });
    return () => {
      active = false;
    };
  }, [user]);

  async function copy(value: string, kind: 'link' | 'code') {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = value;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1800);
  }

  if (loading) {
    return <p className="text-slate-400">Loading…</p>;
  }

  if (!user) {
    return (
      <div className="rounded-[7px] border border-white/8 bg-[rgba(8,10,20,0.55)] p-10">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[7px] bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white">
          <Gift className="h-7 w-7" />
        </div>
        <h1 className="mt-5 font-display text-3xl font-semibold text-white">Invite friends</h1>
        <p className="mt-3 text-slate-300/70">
          Sign in to get your personal invite link and earn credits when friends buy their first
          credit pack.
        </p>
        <Link
          href="/login?next=/invite"
          className="mt-6 inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white"
        >
          Sign in
        </Link>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2 text-slate-400">
        <LoaderCircle className="h-4 w-4 animate-spin" /> Loading your invite link…
      </div>
    );
  }

  const { summary, settings } = data;

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">Invite friends</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-300/70">
            Share your link. When a friend signs up and buys their first credit pack, you both earn
            credits automatically.
          </p>
        </div>
        <div className="flex h-14 w-14 items-center justify-center rounded-[7px] bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_40px_rgba(139,92,246,0.32)]">
          <Gift className="h-7 w-7" />
        </div>
      </div>

      {!data.enabled ? (
        <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          The invite program is currently paused. Your link still works, but rewards are not being
          paid right now.
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'Friends joined', value: summary.total },
          { label: 'Awaiting first purchase', value: summary.pending },
          { label: 'Rewarded invites', value: summary.rewarded },
          { label: 'Credits earned', value: summary.credits_earned },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-[7px] border border-white/8 bg-white/[0.03] p-5"
          >
            <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{stat.label}</div>
            <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
              {stat.value.toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <div className="rounded-[7px] border border-white/8 bg-[rgba(8,10,20,0.55)] p-6">
          <h2 className="font-display text-xl font-semibold text-white">Your invite link</h2>
          <p className="mt-1 text-sm text-slate-400">
            Anyone who signs up through this link is linked to you automatically.
          </p>

          <label htmlFor="invite-link" className="mt-5 block text-xs text-slate-500">
            Share link
          </label>
          <div className="mt-1 flex flex-col gap-2 sm:flex-row">
            <input
              id="invite-link"
              readOnly
              value={shareUrl}
              onFocus={(event) => event.currentTarget.select()}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-white/80 outline-none focus:border-violet-400/40"
            />
            <button
              type="button"
              onClick={() => void copy(shareUrl, 'link')}
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white"
            >
              {copied === 'link' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied === 'link' ? 'Copied' : 'Copy link'}
            </button>
          </div>

          <label htmlFor="invite-code" className="mt-4 block text-xs text-slate-500">
            Invite code
          </label>
          <div className="mt-1 flex flex-col gap-2 sm:flex-row">
            <input
              id="invite-code"
              readOnly
              value={data.code}
              onFocus={(event) => event.currentTarget.select()}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/30 px-3 font-mono text-sm tracking-[0.2em] text-white outline-none focus:border-violet-400/40"
            />
            <button
              type="button"
              onClick={() => void copy(data.code, 'code')}
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-200 hover:bg-white/[0.06]"
            >
              {copied === 'code' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied === 'code' ? 'Copied' : 'Copy code'}
            </button>
          </div>

          <div className="mt-5 space-y-2 rounded-xl border border-white/8 bg-white/[0.02] p-4 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate-400">You earn</span>
              <span className="font-medium text-white">{rewardText(settings.inviter)}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate-400">Your friend receives</span>
              <span className="font-medium text-white">{rewardText(settings.invitee)}</span>
            </div>
          </div>
        </div>

        <div className="rounded-[7px] border border-white/8 bg-[rgba(8,10,20,0.55)] p-6">
          <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-white">
            <Sparkles className="h-5 w-5 text-violet-300" /> How it works
          </h2>
          <ol className="mt-4 space-y-4 text-sm text-slate-300/75">
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-200">
                1
              </span>
              Send your invite link to a friend.
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-200">
                2
              </span>
              They create an account with Google through your link.
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-200">
                3
              </span>
              After their first credit-pack purchase, both rewards are added automatically.
            </li>
          </ol>
          <p className="mt-5 border-t border-white/8 pt-4 text-xs leading-relaxed text-slate-500">
            Rewards are paid once per friend, only on their first paid credit pack. Self-invites and
            duplicate accounts do not qualify.
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-[7px] border border-white/8 bg-[rgba(8,10,20,0.55)]">
        <div className="flex items-center gap-2 border-b border-white/8 px-6 py-4">
          <UserPlus className="h-4 w-4 text-violet-300" />
          <h2 className="font-display text-lg font-semibold text-white">Friends you invited</h2>
        </div>
        {data.invites.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-slate-500">
            No friends yet. Share your link to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.02] text-left text-xs uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th scope="col" className="px-6 py-3">Friend</th>
                  <th scope="col" className="px-6 py-3">Status</th>
                  <th scope="col" className="px-6 py-3 text-right">Their purchase</th>
                  <th scope="col" className="px-6 py-3 text-right">You earned</th>
                  <th scope="col" className="px-6 py-3">Joined</th>
                </tr>
              </thead>
              <tbody>
                {data.invites.map((row) => {
                  const chip = statusChip(row.status);
                  return (
                    <tr key={row.id} className="border-t border-white/5">
                      <td className="px-6 py-3 text-slate-200">{row.invitee_email}</td>
                      <td className="px-6 py-3">
                        <span
                          className={`inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold ${chip.className}`}
                        >
                          {chip.label}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums text-slate-400">
                        {row.purchased_credits != null
                          ? row.purchased_credits.toLocaleString()
                          : '—'}
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums">
                        {row.status === 'rewarded' ? (
                          <span className="text-emerald-300">
                            +{row.reward.toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-slate-500">{formatDate(row.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
