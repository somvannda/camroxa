import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Database, Server, Workflow } from 'lucide-react';
import type { UseQueryResult } from '@tanstack/react-query';

import { HealthSummary } from '@/components/key-pool/health-summary';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  deploymentEnvironmentBadgeClass,
  resolveDeploymentEnvironmentLabel,
} from '@/lib/deployment-environment';
import { cn } from '@/lib/utils';
import type { JobQueueMetricsResponse } from '@/types/job-queue';
import type { HealthStatus } from '@/types/models';

type StatusLevel = HealthStatus['status'];

const STATUS_COLORS: Record<StatusLevel, string> = {
  healthy: 'bg-green-500/10 text-green-400 border-green-500/30',
  degraded: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  unhealthy: 'bg-red-500/10 text-red-400 border-red-500/30',
};

const STATUS_DOT: Record<StatusLevel, string> = {
  healthy: 'bg-green-500',
  degraded: 'bg-yellow-500',
  unhealthy: 'bg-red-500',
};

const STATUS_BORDER: Record<StatusLevel, string> = {
  healthy: 'border-green-500/35',
  degraded: 'border-yellow-500/40',
  unhealthy: 'border-red-500/45',
};

function getStatusLabel(status: StatusLevel | undefined): string {
  if (!status) return 'Unknown';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatUptime(seconds: number | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return '—';
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86_400);
  const hours = Math.floor((total % 86_400) / 3_600);
  const minutes = Math.floor((total % 3_600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatUpdatedAgo(dataUpdatedAt: number | undefined, now = Date.now()): string {
  if (!dataUpdatedAt) return '—';
  const seconds = Math.max(0, Math.floor((now - dataUpdatedAt) / 1000));
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

type WorkerHealth = {
  level: StatusLevel;
  label: string;
  detail: string;
};

function deriveWorkerHealth(
  metrics: JobQueueMetricsResponse | undefined,
): WorkerHealth {
  if (!metrics) {
    return { level: 'unhealthy', label: 'Unknown', detail: 'No worker metrics yet' };
  }
  const alerts = metrics.alerts ?? [];
  const queued = metrics.queue?.queued_depth ?? 0;
  const failed = metrics.queue?.failed ?? 0;
  const busy = metrics.queue?.workers_busy?.length ?? 0;

  if (alerts.length > 0) {
    return {
      level: 'degraded',
      label: 'Attention',
      detail: `${alerts.length} alert${alerts.length === 1 ? '' : 's'} · queue ${queued} · ${busy} busy`,
    };
  }
  if (failed > 0 && queued >= 10) {
    return {
      level: 'degraded',
      label: 'Attention',
      detail: `${failed} failed · queue ${queued}`,
    };
  }
  return {
    level: 'healthy',
    label: 'Healthy',
    detail: `Queue ${queued} · ${busy} busy worker${busy === 1 ? '' : 's'} · ${failed} failed`,
  };
}

type OperationsStatusHeroProps = {
  healthQuery: UseQueryResult<HealthStatus, Error>;
  jobQueueQuery: UseQueryResult<JobQueueMetricsResponse, Error>;
};

export function OperationsStatusHero({
  healthQuery,
  jobQueueQuery,
}: OperationsStatusHeroProps) {
  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 5_000);
    return () => window.clearInterval(id);
  }, []);

  const health = healthQuery.data;
  const worker = deriveWorkerHealth(jobQueueQuery.data);
  const environmentLabel = resolveDeploymentEnvironmentLabel({
    apiEnvironment: health?.environment,
    apiEnvironmentLabel: health?.environment_label,
    hostname: typeof window !== 'undefined' ? window.location.hostname : '',
  });

  const apiReachable = !healthQuery.isError && !!health;
  const apiLevel: StatusLevel = !apiReachable
    ? 'unhealthy'
    : (health?.status ?? 'unhealthy');
  const dbLevel: StatusLevel = !apiReachable
    ? 'unhealthy'
    : health?.database
      ? 'healthy'
      : 'unhealthy';

  const latestUpdate = Math.max(
    healthQuery.dataUpdatedAt || 0,
    jobQueueQuery.dataUpdatedAt || 0,
  );
  const liveStamp = formatUpdatedAgo(latestUpdate || undefined, nowTick);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Live operations</h2>
          <p className="text-sm text-slate-400">
            Platform API, database, and workers — updates automatically.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          Live · updated {liveStamp}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* Platform API */}
        <div className={cn('rounded-2xl border bg-slate-900/60 p-5', STATUS_BORDER[apiLevel])}>
          <div className="flex items-start justify-between gap-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Platform API
            </div>
            <Server className="h-4 w-4 text-slate-500" />
          </div>
          {healthQuery.isLoading ? (
            <Skeleton className="mt-4 h-12 w-40" />
          ) : healthQuery.isError ? (
            <>
              <div className="mt-3 flex items-center gap-3">
                <span className={cn('h-3 w-3 rounded-full', STATUS_DOT.unhealthy)} />
                <div className="text-3xl font-semibold tracking-tight text-white">Down</div>
              </div>
              <p className="mt-3 text-sm text-slate-400">
                Admin could not reach Platform API health endpoint
              </p>
            </>
          ) : (
            <>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span className={cn('h-3 w-3 rounded-full', STATUS_DOT[apiLevel])} />
                <div className="text-3xl font-semibold tracking-tight text-white">
                  {getStatusLabel(apiLevel)}
                </div>
                <Badge
                  variant="outline"
                  className={cn('text-xs', deploymentEnvironmentBadgeClass(environmentLabel))}
                >
                  {environmentLabel}
                </Badge>
              </div>
              <p className="mt-3 text-sm text-slate-400">
                API process reachable · uptime {formatUptime(health?.uptime_seconds)}
              </p>
              <p className="mt-4 text-xs text-slate-500">
                Provider key readiness is shown in the row below
              </p>
            </>
          )}
        </div>

        {/* Database */}
        <div className={cn('rounded-2xl border bg-slate-900/60 p-5', STATUS_BORDER[dbLevel])}>
          <div className="flex items-start justify-between gap-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Database
            </div>
            <Database className="h-4 w-4 text-slate-500" />
          </div>
          {healthQuery.isLoading ? (
            <Skeleton className="mt-4 h-12 w-40" />
          ) : (
            <>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span className={cn('h-3 w-3 rounded-full', STATUS_DOT[dbLevel])} />
                <div className="text-3xl font-semibold tracking-tight text-white">
                  {dbLevel === 'healthy' ? 'Connected' : 'Unreachable'}
                </div>
                <Badge className={cn('text-xs', STATUS_COLORS[dbLevel])}>
                  {getStatusLabel(dbLevel)}
                </Badge>
              </div>
              <p className="mt-3 text-sm text-slate-400">
                PostgreSQL used by Platform API (`SELECT 1` check)
              </p>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                <Activity className="h-3.5 w-3.5" />
                Not a separate service — reported by the API health check
              </div>
            </>
          )}
        </div>

        {/* Workers */}
        <div className={cn('rounded-2xl border bg-slate-900/60 p-5', STATUS_BORDER[worker.level])}>
          <div className="flex items-start justify-between gap-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Workers
            </div>
            <Workflow className="h-4 w-4 text-slate-500" />
          </div>
          {jobQueueQuery.isLoading ? (
            <Skeleton className="mt-4 h-12 w-40" />
          ) : jobQueueQuery.isError ? (
            <div className="mt-4 text-lg font-semibold text-red-300">Unavailable</div>
          ) : (
            <>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span className={cn('h-3 w-3 rounded-full', STATUS_DOT[worker.level])} />
                <div className="text-3xl font-semibold tracking-tight text-white">
                  {worker.label}
                </div>
                <Badge className={cn('text-xs', STATUS_COLORS[worker.level])}>
                  {getStatusLabel(worker.level)}
                </Badge>
              </div>
              <p className="mt-3 text-sm text-slate-400">{worker.detail}</p>
              {(jobQueueQuery.data?.alerts?.length ?? 0) > 0 ? (
                <ul className="mt-3 space-y-1 text-xs text-amber-300/90">
                  {jobQueueQuery.data!.alerts.slice(0, 3).map((alert) => (
                    <li key={alert}>{alert.replace(/_/g, ' ')}</li>
                  ))}
                </ul>
              ) : null}
              <Link
                to="/job-queue"
                className="mt-4 inline-flex items-center text-xs font-medium text-violet-300 hover:text-violet-200"
              >
                Open job queue
                <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Provider key pool</h3>
            <p className="text-xs text-slate-500">
              Key readiness by provider (including unhealthy / critical)
            </p>
          </div>
        </div>
        <HealthSummary
          dashboardRow
          fillRow
          alwaysIncludeCritical
          apiServices={health?.services ?? null}
        />
      </div>
    </section>
  );
}
