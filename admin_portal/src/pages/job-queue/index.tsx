import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useJobQueueJobs,
  useJobQueueMetrics,
  useRecentImageFailures,
} from '@/hooks/use-job-queue';
import type { JobQueueStatusFilter } from '@/types/job-queue';
import { cn } from '@/lib/utils';

const ALERT_LABELS: Record<string, string> = {
  queue_depth_high: 'Queue depth high (≥50)',
  oldest_job_stale: 'Oldest claimable job ≥5 min',
  worker_idle_with_backlog: 'Worker idle with backlog',
  progress_p95_high: '/progress p95 ≥5s',
};

const JOB_TYPE_OPTIONS = [
  'all',
  'execute_batch',
  'draft',
  'suno_submit',
  'retry_song_draft',
  'retry_song_suno',
  'run_image_jobs',
  'run_youtube_uploads',
] as const;

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

function stageBadgeClass(stage: string): string {
  const s = stage.toLowerCase();
  if (s === 'draft') return 'border-sky-500/40 text-sky-300';
  if (s === 'suno') return 'border-fuchsia-500/40 text-fuchsia-300';
  if (s === 'images') return 'border-violet-500/40 text-violet-300';
  return 'border-slate-600 text-slate-300';
}

function shortId(id: string | null | undefined): string {
  if (!id) return '—';
  return id.slice(0, 8);
}

export default function JobQueuePage() {
  const [statusTab, setStatusTab] = useState<JobQueueStatusFilter>('running');
  const [jobType, setJobType] = useState<string>('all');
  const [userFilter, setUserFilter] = useState('');
  const [userQuery, setUserQuery] = useState('');

  const metricsQuery = useJobQueueMetrics();
  const jobsQuery = useJobQueueJobs({
    status: statusTab,
    job_type: jobType === 'all' ? undefined : jobType,
    user: userQuery || undefined,
    limit: 50,
  });
  const imageFailuresQuery = useRecentImageFailures(24);

  const queue = metricsQuery.data?.queue;
  const progress = metricsQuery.data?.progress_latency;
  const alerts = metricsQuery.data?.alerts ?? [];
  const byTypeRows = Object.entries(queue?.by_type ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );
  const jobs = jobsQuery.data?.jobs ?? [];
  const imageFailures = imageFailuresQuery.data?.failures ?? [];

  const isFetching =
    metricsQuery.isFetching ||
    jobsQuery.isFetching ||
    imageFailuresQuery.isFetching;

  const dataUpdatedAt = Math.max(
    metricsQuery.dataUpdatedAt || 0,
    jobsQuery.dataUpdatedAt || 0,
    imageFailuresQuery.dataUpdatedAt || 0,
  );

  const failedCountHint = useMemo(() => {
    const n = queue?.failed ?? 0;
    return n > 0 ? `${n} terminal failed rows` : 'terminal failed rows';
  }, [queue?.failed]);

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Job Queue"
        description="Live durable workers: who is running what, which stage pool is busy, and why jobs failed (including image provider failures)."
        actions={
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">
              {dataUpdatedAt
                ? `Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}`
                : 'Auto-refresh ~8s'}
            </span>
            <Button
              variant="outline"
              onClick={() => {
                void metricsQuery.refetch();
                void jobsQuery.refetch();
                void imageFailuresQuery.refetch();
              }}
              disabled={isFetching}
            >
              <RefreshCw
                className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')}
              />
              Refresh
            </Button>
          </div>
        }
      />

      {metricsQuery.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
      ) : null}

      {metricsQuery.isError ? (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-red-300">
              Unable to load job-queue metrics. Confirm the API is up and your
              admin session is valid.
            </p>
            <Button variant="outline" onClick={() => void metricsQuery.refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {metricsQuery.data && queue && progress ? (
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
              tone={
                queue.queued_depth >= 50
                  ? 'danger'
                  : queue.queued_depth > 0
                    ? 'warning'
                    : 'success'
              }
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
              hint={failedCountHint}
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
                      <TableHead>Worker</TableHead>
                      <TableHead>Stage</TableHead>
                      <TableHead>Job types</TableHead>
                      <TableHead>Users</TableHead>
                      <TableHead className="text-right">Running</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {queue.workers_busy.map((worker) => (
                      <TableRow key={worker.worker_id}>
                        <TableCell className="max-w-[220px] truncate font-mono text-xs">
                          {worker.worker_id}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {(worker.stages?.length
                              ? worker.stages
                              : ['—']
                            ).map((stage) => (
                              <Badge
                                key={`${worker.worker_id}-${stage}`}
                                variant="outline"
                                className={stageBadgeClass(stage)}
                              >
                                {stage}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-300">
                          {(worker.job_types ?? []).join(', ') || '—'}
                        </TableCell>
                        <TableCell className="text-xs text-slate-300">
                          {(worker.user_emails ?? []).slice(0, 3).join(', ') ||
                            '—'}
                          {(worker.user_emails?.length ?? 0) > 3
                            ? ` +${(worker.user_emails?.length ?? 0) - 3}`
                            : ''}
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

          <Card className="border-slate-800 bg-slate-900/40">
            <CardHeader className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle className="text-base text-slate-100">
                  Jobs
                </CardTitle>
                <Tabs
                  value={statusTab}
                  onValueChange={(value) =>
                    setStatusTab(value as JobQueueStatusFilter)
                  }
                >
                  <TabsList>
                    <TabsTrigger value="running">Running</TabsTrigger>
                    <TabsTrigger value="queued">Queued</TabsTrigger>
                    <TabsTrigger value="delayed">Delayed</TabsTrigger>
                    <TabsTrigger value="failed">Failed</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
              <div className="flex flex-wrap gap-3">
                <Select value={jobType} onValueChange={setJobType}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Job type" />
                  </SelectTrigger>
                  <SelectContent>
                    {JOB_TYPE_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option === 'all' ? 'All job types' : option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <form
                  className="flex gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    setUserQuery(userFilter.trim());
                  }}
                >
                  <Input
                    value={userFilter}
                    onChange={(event) => setUserFilter(event.target.value)}
                    placeholder="Filter by user email"
                    className="w-[240px]"
                  />
                  <Button type="submit" variant="outline">
                    Apply
                  </Button>
                </form>
              </div>
            </CardHeader>
            <CardContent>
              {jobsQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : jobsQuery.isError ? (
                <p className="text-sm text-red-300">
                  Failed to load jobs. Try refresh.
                </p>
              ) : jobs.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No {statusTab} jobs match the filters.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Age</TableHead>
                      <TableHead>Stage</TableHead>
                      <TableHead>Job type</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Batch</TableHead>
                      <TableHead>Worker</TableHead>
                      <TableHead>Attempts</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.map((job) => (
                      <TableRow key={job.id}>
                        <TableCell className="whitespace-nowrap text-xs text-slate-400">
                          {formatAge(job.age_seconds)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={stageBadgeClass(job.stage)}
                          >
                            {job.stage}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {job.job_type}
                        </TableCell>
                        <TableCell className="text-xs">
                          <Link
                            to={`/users/${job.user_id}`}
                            className="text-violet-300 hover:underline"
                          >
                            {job.user_email || shortId(job.user_id)}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {job.batch_id ? (
                            <Link
                              to={`/batches/${job.batch_id}`}
                              className="text-sky-300 hover:underline"
                            >
                              {shortId(job.batch_id)}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell className="max-w-[160px] truncate font-mono text-xs text-slate-400">
                          {job.locked_by || '—'}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-xs">
                          {job.attempts}/{job.max_attempts}
                        </TableCell>
                        <TableCell
                          className="max-w-[280px] truncate text-xs text-red-300"
                          title={job.last_error ?? undefined}
                        >
                          {job.last_error || '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

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
                      {byTypeRows.map(([type, counts]) => (
                        <TableRow key={type}>
                          <TableCell className="font-mono text-xs">
                            {type}
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
          </div>

          <Card className="border-slate-800 bg-slate-900/40">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">
                Related: image job failures (24h)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {imageFailuresQuery.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : imageFailures.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No failed image_jobs in the last 24 hours. Provider failures
                  show here even when the queue orchestrator finished.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Age</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Kind</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Batch</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {imageFailures.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell className="whitespace-nowrap text-xs text-slate-400">
                          {formatAge(row.age_seconds)}
                        </TableCell>
                        <TableCell className="text-xs">
                          <Link
                            to={`/users/${row.user_id}`}
                            className="text-violet-300 hover:underline"
                          >
                            {row.user_email || shortId(row.user_id)}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {row.kind}
                          {row.channel_role ? `/${row.channel_role}` : ''}
                        </TableCell>
                        <TableCell className="text-xs">
                          {row.provider || '—'}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {row.batch_id ? (
                            <Link
                              to={`/batches/${row.batch_id}`}
                              className="text-sky-300 hover:underline"
                            >
                              {shortId(row.batch_id)}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell
                          className="max-w-[320px] truncate text-xs text-red-300"
                          title={row.error ?? undefined}
                        >
                          {row.error || '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {metricsQuery.data.note ? (
            <p className="text-xs text-slate-500">{metricsQuery.data.note}</p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
