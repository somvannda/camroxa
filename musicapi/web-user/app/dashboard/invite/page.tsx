"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface RewardRule {
  mode: "percent" | "fixed";
  value: number;
}

interface InviteSettings {
  enabled: boolean;
  inviter: RewardRule;
  invitee: RewardRule;
}

interface InviteRow {
  id: string;
  invitee_email: string;
  status: "pending" | "rewarded" | "skipped" | "rejected";
  purchased_credits: number | null;
  reward: number;
  created_at: string;
  rewarded_at: string | null;
}

interface InviteData {
  enabled: boolean;
  settings: InviteSettings;
  code: string;
  share_path: string;
  summary: {
    total: number;
    pending: number;
    rewarded: number;
    credits_earned: number;
  };
  invites: InviteRow[];
}

function rewardLabel(rule: RewardRule): string {
  if (rule.value <= 0) return "no reward";
  return rule.mode === "percent"
    ? `${rule.value}% of their purchase credits`
    : `${rule.value.toLocaleString()} credits`;
}

function statusChip(status: InviteRow["status"]): { label: string; className: string } {
  switch (status) {
    case "rewarded":
      return {
        label: "Rewarded",
        className: "border-[var(--emerald)]/30 bg-[var(--emerald)]/10 text-[var(--emerald)]",
      };
    case "rejected":
      return {
        label: "Rejected",
        className: "border-red-500/25 bg-red-500/10 text-red-300",
      };
    case "skipped":
      return {
        label: "Skipped",
        className: "border-white/10 bg-white/[0.03] text-white/50",
      };
    default:
      return {
        label: "Waiting for first purchase",
        className: "border-amber-400/25 bg-amber-400/10 text-amber-300",
      };
  }
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
}

function CopyIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function GiftIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="3" y="8" width="18" height="4" rx="1" />
      <path d="M12 8v13M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" />
      <path d="M7.5 8a2.5 2.5 0 0 1 0-5C9.5 3 11 5 12 8c1-3 2.5-5 4.5-5a2.5 2.5 0 0 1 0 5" />
    </svg>
  );
}

export default function InvitePage() {
  const [data, setData] = useState<InviteData | null>(null);
  const [shareUrl, setShareUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState<"link" | "code" | null>(null);

  useEffect(() => {
    apiFetch<InviteData>("/me/invite")
      .then((d) => {
        setData(d);
        setShareUrl(`${window.location.origin}${d.share_path}`);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load invite program"))
      .finally(() => setLoading(false));
  }, []);

  async function copy(value: string, kind: "link" | "code") {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard is unavailable on insecure origins; fall back to selection.
      const el = document.createElement("textarea");
      el.value = value;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(kind);
    setTimeout(() => setCopied(null), 1800);
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-white/50">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-[var(--violet)]" />
        Loading invite program…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
        {error || "Failed to load invite program."}
      </div>
    );
  }

  const { summary, settings } = data;

  return (
    <div className="space-y-6 pb-16">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Invite Friends</h1>
          <p className="mt-1 text-sm text-white/50">
            Share your link. When a friend buys their first credit pack, you both earn credits.
          </p>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-xl grad-bg text-white shadow-lg shadow-purple-900/30">
          <GiftIcon />
        </div>
      </div>

      {!data.enabled && (
        <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-200">
          The invite program is currently paused. Your link still works, but rewards are not being
          paid while it is off.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass rounded-xl p-5">
          <div className="text-xs text-white/45">Friends joined</div>
          <div className="mt-1 text-2xl font-bold text-white">{summary.total.toLocaleString()}</div>
        </div>
        <div className="glass rounded-xl p-5">
          <div className="text-xs text-white/45">Awaiting first purchase</div>
          <div className="mt-1 text-2xl font-bold text-white">{summary.pending.toLocaleString()}</div>
        </div>
        <div className="glass rounded-xl p-5">
          <div className="text-xs text-white/45">Rewarded invites</div>
          <div className="mt-1 text-2xl font-bold text-white">{summary.rewarded.toLocaleString()}</div>
        </div>
        <div className="glass rounded-xl p-5">
          <div className="text-xs text-white/45">Credits earned</div>
          <div className="mt-1 text-2xl font-bold grad-text">
            +{summary.credits_earned.toLocaleString()}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="glass space-y-5 rounded-2xl p-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Your invite link</h2>
            <p className="mt-0.5 text-sm text-white/45">
              Anyone who signs up through this link is linked to you automatically.
            </p>
          </div>

          <div className="space-y-1">
            <label htmlFor="invite-link" className="text-xs text-white/50">
              Share link
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="invite-link"
                readOnly
                value={shareUrl}
                onFocus={(e) => e.currentTarget.select()}
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/80 outline-none focus:border-[var(--violet)]"
              />
              <button
                type="button"
                onClick={() => void copy(shareUrl, "link")}
                className="grad-bg inline-flex shrink-0 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-900/20"
              >
                <CopyIcon />
                {copied === "link" ? "Copied" : "Copy link"}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label htmlFor="invite-code" className="text-xs text-white/50">
              Invite code
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="invite-code"
                readOnly
                value={data.code}
                onFocus={(e) => e.currentTarget.select()}
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-sm tracking-[0.2em] text-white outline-none focus:border-[var(--violet)]"
              />
              <button
                type="button"
                onClick={() => void copy(data.code, "code")}
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/80 hover:bg-white/5"
              >
                <CopyIcon />
                {copied === "code" ? "Copied" : "Copy code"}
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-sm text-white/60">
            <div className="flex items-center justify-between gap-3">
              <span>You earn</span>
              <span className="font-semibold text-white">{rewardLabel(settings.inviter)}</span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span>Your friend receives</span>
              <span className="font-semibold text-white">{rewardLabel(settings.invitee)}</span>
            </div>
          </div>
        </div>

        <div className="glass space-y-4 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white">How it works</h2>
          <ol className="space-y-3 text-sm text-white/60">
            <li className="flex gap-3">
              <span className="grad-bg flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
                1
              </span>
              Send your link to a friend.
            </li>
            <li className="flex gap-3">
              <span className="grad-bg flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
                2
              </span>
              They sign in with Google through your link.
            </li>
            <li className="flex gap-3">
              <span className="grad-bg flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
                3
              </span>
              After their first credit-pack purchase, both rewards are added automatically.
            </li>
          </ol>
          <p className="border-t border-white/10 pt-3 text-xs text-white/40">
            Rewards are paid once per friend, only on their first paid credit pack. Self-invites
            and duplicate accounts do not qualify.
          </p>
        </div>
      </div>

      <div className="glass overflow-hidden rounded-2xl">
        <div className="border-b border-white/10 px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Friends you invited</h2>
          <p className="mt-0.5 text-sm text-white/45">
            Pending friends become rewards after their first purchase.
          </p>
        </div>
        {data.invites.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-white/45">
            No friends yet. Share your link to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.03] text-left text-xs text-white/45">
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
                      <td className="px-6 py-3 text-white/80">{row.invitee_email}</td>
                      <td className="px-6 py-3">
                        <span
                          className={`inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${chip.className}`}
                        >
                          {chip.label}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums text-white/60">
                        {row.purchased_credits != null ? row.purchased_credits.toLocaleString() : "—"}
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums">
                        {row.status === "rewarded" ? (
                          <span className="text-[var(--emerald)]">+{row.reward.toLocaleString()}</span>
                        ) : (
                          <span className="text-white/40">—</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-white/45">{formatDate(row.created_at)}</td>
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
