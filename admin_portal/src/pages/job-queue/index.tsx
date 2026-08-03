import {
  Activity,
  AlertTriangle,
  ListOrdered,
  RefreshCw,
  Timer,
  Workflow,
} from 'lucide-react';

import { PageHeader } from '@/components/shared/page-header';
import { StatCard } from '@/components/shared/stat-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useJobQueueMetrics } from '@/hooks/use-job-queue';

const ALERT_LABELS: Record<string, string> = {
  queue_depth_high: 'Queue depth high (≥50)',
  oldest_job_stale: 'Oldest claimable job ≥5 min',
  worker_idle_with_backlog: 'Worker idle with backlog',
  progress_p95_high: '/progress p95 ≥5s',
};

function formatMs(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${Math.round(value)} ms`;
}

function formatAge(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function statusTone(
  status: string,
): 'default' | 'danger' | 'warning' | 'success' {
  if (status === 'failed') return 'danger';
  if (status === 'running') return 'success';
  if (status === 'delayed' || status === 'queued') return 'warning';
  return 'default';
}

export default function JobQueuePage() {
  const { data, isLoading, isError, isFetching, refetch, dataUpdatedAt } =
    useJobQueueMetrics();

  const queue = data?.queue;
  const progress = data?.progress_latency;
  const alerts = data?.alerts ?? [];
  const byTypeRows = Object.entries(queue?.by_type ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Job Queue"
        description="Live depth for camxora-worker, busy locks, and /progress latency samples from this API process."
        actions={
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">
              {dataUpdatedAt
                ? `Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}`
                : 'Auto-refresh 15s'}
            </span>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
              />
              Refresh
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      ) : null}

      {isError ? (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-red-300">
              Unable to load job-queue metrics. Confirm the API is up and your
              admin session is valid.
            </p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {data && queue && progress ? (
        <>
          {alerts.length > 0 ? (
            <Card className="border-amber-500/30 bg-amber-500/5">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base text-amber-200">
                  <AlertTriangle className="h-4 w-4" />
                  Alerts
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {alerts.map((alert) => (
                  <Badge
                    key={alert}
                    variant="outline"
                    className="border-amber-500/40 bg-amber-500/10 text-amber-200"
                  >
                    {ALERT_LABELS[alert] ?? alert}
                  </Badge>
                ))}
              </CardContent>
            </Card>
          ) : (
            <Card className="border-emerald-500/20 bg-emerald-500/5">
              <CardContent className="flex items-center gap-2 p-4 text-sm text-emerald-300">
                <Activity className="h-4 w-4" />
                No threshold alerts
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Queued depth"
              value={queue.queued_depth}
              hint="queued + delayed claimable"
              icon={ListOrdered}
              tone={queue.queued_depth >= 50 ? 'danger' : queue.queued_depth > 0 ? 'warning' : 'success'}
            />
            <StatCard
              label="Running"
              value={queue.running}
              hint={
                queue.workers_busy.length
                  ? `${queue.workers_busy.length} busy worker lock(s)`
                  : 'no locks'
              }
              icon={Workflow}
              tone={queue.running > 0 ? 'success' : 'default'}
            />
            <StatCard
              label="Failed"
              value={queue.failed}
              hint="terminal failed rows"
              icon={AlertTriangle}
              tone={queue.failed > 0 ? 'danger' : 'default'}
            />
            <StatCard
              label="/progress p95"
              value={formatMs(progress.p95_ms)}
              hint={`${progress.samples} sample(s) · p50 ${formatMs(progress.p50_ms)}`}
              icon={Timer}
              tone={
                progress.p95_ms != null && progress.p95_ms >= 5000
                  ? 'danger'
                  : progress.p95_ms != null && progress.p95_ms >= 2000
                    ? 'warning'
                    : 'default'
              }
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="border-slate-800 bg-slate-900/40">
              <CardHeader>
                <CardTitle className="text-base text-slate-100">
                  Status breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {Object.keys(queue.by_status).length === 0 ? (
                  <p className="text-sm text-slate-500">No active/failed rows.</p>
                ) : (
                  Object.entries(queue.by_status)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([status, count]) => (
                      <Badge
                        key={status}
                        variant="outline"
                        className={
                          statusTone(status) === 'danger'
                            ? 'border-red-500/40 text-red-300'
                            : statusTone(status) === 'warning'
                              ? 'border-amber-500/40 text-amber-300'
                              : statusTone(status) === 'success'
                                ? 'border-emerald-500/40 text-emerald-300'
                                : 'border-slate-600 text-slate-300'
                        }
                      >
                        {status}: {count}
                      </Badge>
                    ))
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/40">
              <CardHeader>
                <CardTitle className="text-base text-slate-100">
                  Oldest claimable
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-slate-300">
                {queue.oldest_claimable ? (
                  <>
                    <div>
                      <span className="text-slate-500">Type · </span>
                      {queue.oldest_claimable.job_type}
                    </div>
                    <div>
                      <span className="text-slate-500">Age · </span>
                      {formatAge(queue.oldest_claimable.age_seconds)}
                    </div>
                    <div className="font-mono text-xs text-slate-500">
                      {queue.oldest_claimable.id}
                    </div>
                  </>
                ) : (
                  <p className="text-slate-500">Queue is empty.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="border-slate-800 bg-slate-900/40">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">
                By job type
              </CardTitle>
            </CardHeader>
            <CardContent>
              {byTypeRows.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No queued, delayed, or running jobs.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Job type</TableHead>
                      <TableHead className="text-right">Queued</TableHead>
                      <TableHead className="text-right">Delayed</TableHead>
                      <TableHead className="text-right">Running</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {byTypeRows.map(([jobType, counts]) => (
                      <TableRow key={jobType}>
                        <TableCell className="font-mono text-xs">
                          {jobType}
                        </TableCell>
                        <TableCell className="text-right">
                          {counts.queued ?? 0}
                        </TableCell>
                        <TableCell className="text-right">
                          {counts.delayed ?? 0}
                        </TableCell>
                        <TableCell className="text-right">
                          {counts.running ?? 0}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-slate-900/40">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">
                Busy workers
              </CardTitle>
            </CardHeader>
            <CardContent>
              {queue.workers_busy.length === 0 ? (
                <p className="text-sm text-slate-500">No running locks.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Worker id</TableHead>
                      <TableHead className="text-right">Running jobs</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {queue.workers_busy.map((worker) => (
                      <TableRow key={worker.worker_id}>
                        <TableCell className="font-mono text-xs">
                          {worker.worker_id}
                        </TableCell>
                        <TableCell className="text-right">
                          {worker.running_jobs}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {data.note ? (
            <p className="text-xs text-slate-500">{data.note}</p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
