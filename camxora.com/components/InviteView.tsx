"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchInviteProgram,
  type InviteProgram,
  type InviteRewardRule,
} from "@/lib/invite-api";

function rewardText(rule: InviteRewardRule): string {
  if (rule.value <= 0) return "No reward";
  return rule.mode === "percent"
    ? `${rule.value}% of their purchase credits`
    : `${rule.value.toLocaleString()} credits`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
}

function statusLabel(status: string): string {
  if (status === "rewarded") return "Rewarded";
  if (status === "rejected") return "Rejected";
  if (status === "skipped") return "Skipped";
  return "Awaiting first purchase";
}

export function InviteView() {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<InviteProgram | null>(null);
  const [shareUrl, setShareUrl] = useState("");
  const [copied, setCopied] = useState<"link" | "code" | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoading(true);
    setError("");
    fetchInviteProgram()
      .then((program) => {
        if (!active) return;
        setData(program);
        const sharePath = program.share_path.replace(/^\/register(?=\?|$)/, "/signup");
        setShareUrl(`${window.location.origin}${sharePath}`);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load invites");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  async function copy(value: string, kind: "link" | "code") {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1800);
  }

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-gift" /></span>
          <h1>Invite friends</h1>
          <p>
            Sign in to get your personal invite link and earn credits when friends
            buy their first credit pack.
          </p>
          <Link className="btn btn-primary" href="/login?next=/invite">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  if (loading || !data) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading your invite link…</p>;
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Rewards</div>
          <h1>Invite friends.</h1>
          <p>
            Share your link. When a friend signs up and buys their first credit
            pack, you both earn credits automatically.
          </p>
        </div>
        <span className="invite-hero-icon"><Icon name="fa-gift" /></span>
      </div>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">
          {error}
        </p>
      ) : null}

      {!data.enabled ? (
        <div className="invite-paused">
          The invite program is currently paused. Your link still works, but rewards
          are not being paid right now.
        </div>
      ) : null}

      <div className="stats-row invite-stats">
        <div className="stat-card">
          <b>{data.summary.total.toLocaleString()}</b>
          <span>Friends joined</span>
        </div>
        <div className="stat-card">
          <b>{data.summary.pending.toLocaleString()}</b>
          <span>Awaiting first purchase</span>
        </div>
        <div className="stat-card">
          <b>{data.summary.rewarded.toLocaleString()}</b>
          <span>Rewarded invites</span>
        </div>
        <div className="stat-card">
          <b>{data.summary.credits_earned.toLocaleString()}</b>
          <span>Credits earned</span>
        </div>
      </div>

      <div className="invite-grid">
        <section className="panel invite-panel">
          <h2>Your invite link</h2>
          <p>Anyone who signs up through this link is linked to you automatically.</p>

          <label htmlFor="invite-link">Share link</label>
          <div className="invite-copy-row">
            <input
              id="invite-link"
              readOnly
              value={shareUrl}
              onFocus={(event) => event.currentTarget.select()}
            />
            <button className="btn btn-primary" type="button" onClick={() => copy(shareUrl, "link")}>
              <Icon name={copied === "link" ? "fa-check" : "fa-copy"} />
              {copied === "link" ? "Copied" : "Copy link"}
            </button>
          </div>

          <label htmlFor="invite-code">Invite code</label>
          <div className="invite-copy-row">
            <input
              id="invite-code"
              readOnly
              className="invite-code"
              value={data.code}
              onFocus={(event) => event.currentTarget.select()}
            />
            <button className="btn btn-ghost" type="button" onClick={() => copy(data.code, "code")}>
              <Icon name={copied === "code" ? "fa-check" : "fa-copy"} />
              {copied === "code" ? "Copied" : "Copy code"}
            </button>
          </div>

          <div className="invite-rewards">
            <div>
              <span>You earn</span>
              <b>{rewardText(data.settings.inviter)}</b>
            </div>
            <div>
              <span>Your friend receives</span>
              <b>{rewardText(data.settings.invitee)}</b>
            </div>
          </div>
        </section>

        <section className="panel invite-panel">
          <h2><Icon name="fa-wand-magic-sparkles" /> How it works</h2>
          <ol className="invite-steps">
            <li><span>1</span> Send your invite link to a friend.</li>
            <li><span>2</span> They create an account through your link.</li>
            <li><span>3</span> After their first credit-pack purchase, both rewards are added automatically.</li>
          </ol>
          <p className="invite-note">
            Rewards are paid once per friend, only on their first paid credit pack.
            Self-invites and duplicate accounts do not qualify.
          </p>
        </section>
      </div>

      <section className="panel invite-friends">
        <div className="sec-head">
          <h2><Icon name="fa-user-plus" /> Friends you invited</h2>
        </div>
        {!data.invites.length ? (
          <div className="invite-empty">
            No friends yet. Share your link to get started.
          </div>
        ) : (
          <div className="invite-table-wrap">
            <table className="invite-table">
              <thead>
                <tr>
                  <th>Friend</th>
                  <th>Status</th>
                  <th className="right">Their purchase</th>
                  <th className="right">You earned</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {data.invites.map((row) => (
                  <tr key={row.id}>
                    <td>{row.invitee_email}</td>
                    <td><span className={`invite-status ${row.status}`}>{statusLabel(row.status)}</span></td>
                    <td className="right">{row.purchased_credits != null ? row.purchased_credits.toLocaleString() : "—"}</td>
                    <td className="right">
                      {row.status === "rewarded" ? (
                        <span className="invite-earned">+{row.reward.toLocaleString()}</span>
                      ) : "—"}
                    </td>
                    <td>{formatDate(row.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
