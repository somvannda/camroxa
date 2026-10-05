"use client";

import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/Feedback";
import { dateTime, num } from "@/lib/format";

interface SystemInfo {
  ok: boolean;
  environment: string;
  uptime_seconds: number;
  time: string;
  db: { ok: boolean; latency_ms: number };
  queue: { driver: string; in_memory_jobs: number };
  accounts: number;
  jobs: { total: number; by_status: Record<string, number> };
  suno: {
    active: number;
    waiting: number;
    capacity: number;
    max_concurrent_per_user: number;
    max_concurrent_per_account: number;
    by_account: Record<string, number>;
  };
  storage: { configured: boolean; bucket: string; prefix: string; cdn: boolean };
  storage_configured: boolean;
  captcha_configured: boolean;
  alerts_telegram_configured: boolean;
}

function uptime(sec: number): string {
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

const JOB_TONES: Record<string, BadgeTone> = {
  complete: "success",
  error: "danger",
  running: "info",
  streaming: "info",
  pending: "warning",
};

export default function SystemPage() {
  const { data, loading, error, reload } = useResource<SystemInfo>(() =>
    apiFetch<SystemInfo>("/admin/system"),
  );

  if (loading) return <LoadingState />;
  if (error || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="System Health" description="Live service status" />
        <ErrorState message={error || "Failed to load"} onRetry={reload} />
      </div>
    );
  }

  const suno = data.suno;
  const byAccount = Object.entries(suno.by_account ?? {});

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Health"
        description={`Live service status · checked ${dateTime(data.time)}`}
        actions={
          <Button variant="secondary" onClick={reload}>
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="API / Database"
          value={
            <Badge tone={data.db.ok ? "success" : "danger"}>
              {data.db.ok ? "Healthy" : "Unreachable"}
            </Badge>
          }
          hint={`DB ${data.db.latency_ms} ms`}
        />
        <StatCard label="Environment" value={<span className="text-2xl">{data.environment}</span>} />
        <StatCard label="Uptime" value={<span className="text-2xl">{uptime(data.uptime_seconds)}</span>} />
        <StatCard label="Suno accounts (pooled)" value={num(data.accounts)} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-[var(--muted)]">Job queue</h2>
          <div className="flex flex-wrap gap-2">
            <Badge tone="neutral">driver: {data.queue.driver}</Badge>
            <Badge tone="neutral">in-memory: {num(data.queue.in_memory_jobs)}</Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.keys(data.jobs.by_status).length === 0 ? (
              <span className="text-sm text-[var(--muted)]">No in-memory jobs.</span>
            ) : (
              Object.entries(data.jobs.by_status).map(([status, count]) => (
                <span key={status} className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                  <Badge tone={JOB_TONES[status] ?? "neutral"}>{status}</Badge>
                  {num(count)}
                </span>
              ))
            )}
          </div>
        </Card>

        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-[var(--muted)]">Suno concurrency</h2>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-[var(--muted)]">Active</div>
              <div className="text-xl font-bold">{num(suno.active)}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--muted)]">Waiting</div>
              <div className="text-xl font-bold">{num(suno.waiting)}</div>
            </div>
            <div>
              <div className="text-xs text-[var(--muted)]">Capacity</div>
              <div className="text-xl font-bold">{num(suno.capacity)}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-[var(--muted)]">
            <Badge tone="neutral">per user: {num(suno.max_concurrent_per_user)}</Badge>
            <Badge tone="neutral">per account: {num(suno.max_concurrent_per_account)}</Badge>
          </div>
          {byAccount.length > 0 && (
            <div className="space-y-1">
              {byAccount.map(([account, inflight]) => (
                <div key={account} className="flex justify-between text-xs text-[var(--muted)]">
                  <span className="font-mono">{account}</span>
                  <span>{num(inflight)} in flight</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-[var(--muted)]">Media storage</h2>
          <div className="flex flex-wrap gap-2">
            <Badge tone={data.storage.configured ? "success" : "danger"}>
              {data.storage.configured ? "configured" : "not configured"}
            </Badge>
            {data.storage.cdn && <Badge tone="info">CDN</Badge>}
          </div>
          <div className="text-xs text-[var(--muted)]">
            bucket: <span className="font-mono">{data.storage.bucket || "—"}</span>
            <br />
            prefix: <span className="font-mono">{data.storage.prefix || "—"}</span>
          </div>
          {!data.storage.configured && (
            <p className="text-xs text-red-300">
              Audio generation will fail until object storage is configured.
            </p>
          )}
        </Card>

        <Card className="space-y-3 p-5">
          <h2 className="text-sm font-semibold text-[var(--muted)]">Integrations</h2>
          <div className="flex flex-wrap gap-2">
            <Badge tone={data.captcha_configured ? "success" : "warning"}>
              {data.captcha_configured ? "2Captcha configured" : "2Captcha missing"}
            </Badge>
            <Badge tone={data.alerts_telegram_configured ? "success" : "neutral"}>
              {data.alerts_telegram_configured ? "Telegram alerts configured" : "Telegram alerts off"}
            </Badge>
          </div>
          <p className="text-xs text-[var(--muted)]">
            Manage keys on the{" "}
            <Link href="/admin/settings" className="text-[var(--violet)] hover:underline">
              Settings
            </Link>{" "}
            page.
          </p>
        </Card>
      </div>
    </div>
  );
}
