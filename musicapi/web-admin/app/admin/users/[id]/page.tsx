"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card, StatCard } from "@/components/ui/Card";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { dateTime, num, percent } from "@/lib/format";

interface KeyRow {
  id: string;
  name: string;
  key_prefix: string;
  credits: number;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  credits_expire_at: string | null;
}

interface LedgerRow {
  id: string;
  amount: number;
  type: string;
  description: string | null;
  job_id: string | null;
  created_at: string;
}

interface UserDetail {
  user: {
    id: string;
    email: string;
    name: string | null;
    role: string;
    status: string;
    language: string;
    created_at: string;
    email_subscription: boolean;
    credit_alert_thresholds: number[];
    has_google: boolean;
    has_password: boolean;
  };
  credits: number;
  keys: KeyRow[];
  usage: {
    total: number;
    complete: number;
    failed: number;
    credits_spent: number;
    last_activity: string | null;
  };
  transactions: LedgerRow[];
  invite: {
    code: string | null;
    invited: number;
    rewarded: number;
    credits_earned: number;
    referred_by: {
      email: string;
      status: string;
      code: string;
      created_at: string;
    } | null;
  };
}

const TYPE_TONES: Record<string, BadgeTone> = {
  purchase: "success",
  adjust: "warning",
  spend: "neutral",
  refund: "info",
  referral: "success",
};

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, loading, error, reload } = useResource<UserDetail>(
    () => apiFetch<UserDetail>(`/admin/users/${id}`),
    [id],
  );

  if (loading) return <LoadingState />;
  if (error || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="User" description="Account detail" />
        <ErrorState message={error || "Failed to load"} onRetry={reload} />
      </div>
    );
  }

  const u = data.user;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/users"
          className="text-xs text-[var(--muted)] hover:text-white hover:underline"
        >
          ← Back to users
        </Link>
      </div>

      <PageHeader
        title={u.email}
        description={
          <span>
            {u.name ? `${u.name} · ` : ""}
            joined {dateTime(u.created_at)}
          </span>
        }
        actions={
          <span className="flex items-center gap-2">
            <Badge tone={u.role === "admin" ? "info" : "neutral"}>{u.role}</Badge>
            <Badge tone={u.status === "active" ? "success" : "danger"}>{u.status}</Badge>
          </span>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Credits" value={num(data.credits)} />
        <StatCard label="Requests" value={num(data.usage.total)} />
        <StatCard label="Success rate" value={percent(data.usage.complete, data.usage.total)} />
        <StatCard label="Credits spent" value={num(data.usage.credits_spent)} />
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">Profile</h2>
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs text-[var(--muted)]">Login methods</dt>
            <dd className="mt-0.5">
              {[u.has_google ? "Google" : null, u.has_password ? "Password" : null]
                .filter(Boolean)
                .join(", ") || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Language</dt>
            <dd className="mt-0.5">{u.language || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Email subscription</dt>
            <dd className="mt-0.5">{u.email_subscription ? "On" : "Off"}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Credit alert thresholds</dt>
            <dd className="mt-0.5">
              {u.credit_alert_thresholds?.length
                ? u.credit_alert_thresholds.join(", ")
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Last activity</dt>
            <dd className="mt-0.5">{data.usage.last_activity ? dateTime(data.usage.last_activity) : "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Failed requests</dt>
            <dd className="mt-0.5">{num(data.usage.failed)}</dd>
          </div>
        </dl>
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">Invite program</h2>
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <dt className="text-xs text-[var(--muted)]">Invite code</dt>
            <dd className="mt-0.5 font-mono text-xs">{data.invite.code ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Friends invited</dt>
            <dd className="mt-0.5">{num(data.invite.invited)}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Rewarded</dt>
            <dd className="mt-0.5">{num(data.invite.rewarded)}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Invite credits earned</dt>
            <dd className="mt-0.5">{num(data.invite.credits_earned)}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--muted)]">Referred by</dt>
            <dd className="mt-0.5">
              {data.invite.referred_by ? (
                <span>
                  {data.invite.referred_by.email}{" "}
                  <Badge
                    tone={
                      data.invite.referred_by.status === "rewarded"
                        ? "success"
                        : data.invite.referred_by.status === "rejected"
                          ? "danger"
                          : "warning"
                    }
                  >
                    {data.invite.referred_by.status}
                  </Badge>
                </span>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">
          API keys ({data.keys.length})
        </h2>
        {data.keys.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No keys.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-[var(--muted)]">
                <tr>
                  <th scope="col" className="py-2 pr-4">Name</th>
                  <th scope="col" className="py-2 pr-4">Prefix</th>
                  <th scope="col" className="py-2 pr-4 text-right">Credits</th>
                  <th scope="col" className="py-2 pr-4">Status</th>
                  <th scope="col" className="py-2 pr-4">Last used</th>
                </tr>
              </thead>
              <tbody>
                {data.keys.map((k) => (
                  <tr key={k.id} className="border-t border-[var(--border)]">
                    <td className="py-2 pr-4">{k.name}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-[var(--muted)]">
                      {k.key_prefix}…
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">{num(k.credits)}</td>
                    <td className="py-2 pr-4">
                      <Badge tone={k.is_active ? "success" : "danger"}>
                        {k.is_active ? "active" : "inactive"}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 text-xs text-[var(--muted)]">
                      {k.last_used_at ? dateTime(k.last_used_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-semibold text-[var(--muted)]">Recent credit activity</h2>
        {data.transactions.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No transactions.</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {data.transactions.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-4 py-2 text-sm">
                <span className="flex items-center gap-3">
                  <Badge tone={TYPE_TONES[t.type] ?? "neutral"}>{t.type}</Badge>
                  <span className="text-[var(--muted)]">{t.description ?? "—"}</span>
                </span>
                <span className="flex items-center gap-4 whitespace-nowrap">
                  <span className="text-xs text-[var(--muted)]">{dateTime(t.created_at)}</span>
                  <span
                    className={`tabular-nums ${
                      t.amount > 0 ? "text-emerald-300" : t.amount < 0 ? "text-red-300" : ""
                    }`}
                  >
                    {t.amount > 0 ? "+" : ""}
                    {num(t.amount)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
