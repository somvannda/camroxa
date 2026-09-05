import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { Pagination } from '@/components/data-table/pagination';
import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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
  useRetryAllUploadSweepStatus,
  useRetryUploadJob,
  useStartRetryAllUploads,
  useStreamingUploadJobs,
} from '@/hooks/use-streaming';
import type { StreamingUploadJob } from '@/hooks/use-streaming';
import { toast } from '@/hooks/use-toast';

function formatWhen(value?: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function apiErrorMessage(err: unknown, fallback: string): string {
  const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
  return axiosError.response?.data?.error?.message ?? fallback;
}

function kindTone(kind: string): string {
  const k = kind.toLowerCase();
  if (k === 'mp3_ok') return 'border-emerald-500/30 text-emerald-300';
  if (k === 'mp3_alt') return 'border-sky-500/30 text-sky-300';
  if (k === 'cover') return 'border-violet-500/30 text-violet-300';
  return 'border-slate-700 text-slate-300';
}

function JobCard({
  job,
  onRetry,
  retryPending,
}: {
  job: StreamingUploadJob;
  onRetry: (id: string) => void;
  retryPending: boolean;
}) {
  const title =
    job.song_title ||
    (job.song_batch_index != null ? `Track #${job.song_batch_index + 1}` : null) ||
    job.stream_album_name ||
    job.kind;

  return (
    <Card className="border-slate-800 bg-slate-900/50">
      <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-slate-100">{title}</p>
            <Badge variant="outline" className={kindTone(job.kind)}>
              {job.kind}
            </Badge>
            <Badge
              variant={
                job.status === 'failed'
                  ? 'destructive'
                  : job.status === 'success'
                    ? 'default'
                    : 'secondary'
              }
            >
              {job.status}
            </Badge>
            {(job.attempt_count ?? 0) > 1 ? (
              <Badge variant="outline" className="border-slate-700 text-slate-400">
                ×{job.attempt_count}
              </Badge>
            ) : null}
          </div>

          <div className="grid gap-1 text-xs text-slate-400 sm:grid-cols-2">
            <div>
              User:{' '}
              {job.user_id ? (
                <Link to={`/users/${job.user_id}`} className="text-blue-400 hover:underline">
                  {job.user_display_name || job.user_email || job.user_id.slice(0, 8)}
                </Link>
              ) : (
                '—'
              )}
            </div>
            <div>Email: {job.user_email || '—'}</div>
            <div>
              Album:{' '}
              {job.stream_album_name || job.song_album || '—'}
              {job.stream_channel_role ? ` · ${job.stream_channel_role}` : ''}
            </div>
            <div>
              Publish:{' '}
              {job.stream_track_publish_status ||
                job.stream_album_publish_status ||
                '—'}
              {job.stream_track_variant ? ` · ${job.stream_track_variant}` : ''}
            </div>
            <div>
              Batch:{' '}
              {job.batch_id ? (
                <Link
                  to={`/batches/${job.batch_id}`}
                  className="font-mono text-blue-400 hover:underline"
                >
                  {job.batch_id.slice(0, 8)}…
                </Link>
              ) : (
                '—'
              )}
            </div>
            <div>
              Song:{' '}
              {job.song_id ? (
                <Link
                  to={`/songs/${job.song_id}`}
                  className="font-mono text-blue-400 hover:underline"
                >
                  {job.song_id.slice(0, 8)}…
                </Link>
              ) : (
                '—'
              )}
            </div>
            <div>Created: {formatWhen(job.created_at)}</div>
            <div>Updated: {formatWhen(job.updated_at)}</div>
          </div>

          {job.storage_key ? (
            <p className="break-all font-mono text-[11px] text-slate-500">{job.storage_key}</p>
          ) : null}
          {job.source_url ? (
            <p className="truncate text-[11px] text-slate-600" title={job.source_url}>
              source: {job.source_url}
            </p>
          ) : null}
          {job.error ? <p className="text-sm text-red-300">{job.error}</p> : null}
          <p className="font-mono text-[10px] text-slate-600">{job.id}</p>
        </div>

        {job.status === 'failed' && String(job.kind).startsWith('mp3_') ? (
          <Button
            size="sm"
            variant="outline"
            disabled={retryPending}
            onClick={() => onRetry(job.id)}
          >
            Retry upload
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

const PAGE_SIZES = [25, 50, 100];

export default function StreamingUploadJobsPage() {
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'pending' | 'running' | 'success' | 'failed'
  >('all');
  const [kindFilter, setKindFilter] = useState<'all' | 'mp3_ok' | 'mp3_alt' | 'cover'>('all');
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => window.clearTimeout(handle);
  }, [q]);

  // Filters/search/page-size change -> back to page 1.
  useEffect(() => {
    setPage(1);
  }, [debouncedQ, statusFilter, kindFilter, pageSize]);

  const { data, isLoading, isError, refetch } = useStreamingUploadJobs({
    page,
    pageSize,
    status: statusFilter,
    kind: kindFilter,
    q: debouncedQ || undefined,
  });
  const retry = useRetryUploadJob();
  const startSweep = useStartRetryAllUploads();
  const sweep = useRetryAllUploadSweepStatus();
  const queryClient = useQueryClient();
  const sweepRunning = sweep.data?.running ?? false;
  const prevSweepRunning = useRef<boolean | undefined>(undefined);

  const refreshCounts = () => {
    void queryClient.invalidateQueries({ queryKey: ['streaming-upload-sweep-status'] });
  };

  // Auto-refresh the job list once a background sweep finishes.
  useEffect(() => {
    const was = prevSweepRunning.current;
    prevSweepRunning.current = sweepRunning;
    if (was === true && !sweepRunning) {
      refetch();
      refreshCounts();
    }
  }, [sweepRunning, refetch]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // Stay on the last valid page if the sweep/filters shrink the result set.
  useEffect(() => {
    const pages = Math.max(1, Math.ceil(total / pageSize));
    if (page > pages) setPage(pages);
  }, [total, pageSize, page]);

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Streaming Upload Jobs"
        description="Background catalog uploads (mp3_ok, mp3_alt, cover) from Suno callbacks and image generation — with song, album, user, and publish detail."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search user, song, batch…"
              className="w-56"
            />
            <Select
              value={kindFilter}
              onValueChange={(value) => setKindFilter(value as typeof kindFilter)}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Kind" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All kinds</SelectItem>
                <SelectItem value="mp3_ok">mp3_ok</SelectItem>
                <SelectItem value="mp3_alt">mp3_alt</SelectItem>
                <SelectItem value="cover">cover</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as typeof statusFilter)}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => setPageSize(Number(value))}
            >
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Per page" />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size} / page
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              disabled={sweepRunning || startSweep.isPending}
              onClick={() =>
                startSweep.mutate(undefined, {
                  onSuccess: (res) => {
                    if (res.started) {
                      toast({
                        title: 'Retry sweep started',
                        description: `${res.total} failed MP3 upload(s) queued — running in the background.`,
                      });
                    } else if (res.running) {
                      toast({ title: 'A retry sweep is already running.' });
                    } else {
                      toast({ title: 'No failed MP3 uploads to retry.' });
                    }
                  },
                  onError: (err: unknown) =>
                    toast({
                      title: apiErrorMessage(err, 'Failed to start retry sweep'),
                      variant: 'destructive',
                    }),
                })
              }
            >
              {sweepRunning || startSweep.isPending ? 'Sweeping…' : 'Retry all failed'}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                refetch();
                refreshCounts();
              }}
            >
              Refresh
            </Button>
          </div>
        }
      />

      {sweep.data ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="flex flex-wrap items-center gap-x-10 gap-y-4 p-4">
            <div className="min-w-28 space-y-0.5">
              <p className="text-xs text-slate-500">Failed MP3 now</p>
              <p className="text-2xl font-semibold text-red-300">
                {(sweep.data.failed_mp3_now ?? 0).toLocaleString()}
              </p>
            </div>
            <div className="min-w-28 space-y-0.5">
              <p className="text-xs text-slate-500">Recovered by retry (all time)</p>
              <p className="text-2xl font-semibold text-emerald-300">
                {(sweep.data.retried_success_total ?? 0).toLocaleString()}
              </p>
            </div>
            <div className="min-w-28 space-y-0.5">
              <p className="text-xs text-slate-500">Recovered this sweep</p>
              <p className="text-2xl font-semibold text-slate-100">
                {sweep.data.succeeded.toLocaleString()}
              </p>
            </div>
            <div className="ml-auto min-w-56 space-y-1 text-right">
              <Badge
                variant={sweepRunning ? 'default' : sweep.data.total > 0 ? 'secondary' : 'outline'}
              >
                {sweepRunning
                  ? 'Retry sweep in progress'
                  : sweep.data.total > 0
                    ? 'Last sweep finished'
                    : 'No sweep run yet'}
              </Badge>
              <p className="text-xs text-slate-400">
                {sweepRunning ? (
                  <>
                    {sweep.data.scanned.toLocaleString()} of{' '}
                    {sweep.data.total.toLocaleString()} scanned ·{' '}
                    {sweep.data.succeeded.toLocaleString()} ok ·{' '}
                    {sweep.data.still_failed.toLocaleString()} failed
                  </>
                ) : sweep.data.finished_at ? (
                  <>
                    {sweep.data.succeeded.toLocaleString()} ok ·{' '}
                    {sweep.data.still_failed.toLocaleString()} failed of{' '}
                    {sweep.data.total.toLocaleString()} · finished{' '}
                    {formatWhen(sweep.data.finished_at)}
                  </>
                ) : sweep.data.total > 0 ? (
                  <>started {formatWhen(sweep.data.started_at)}</>
                ) : (
                  'Click “Retry all failed” to sweep the backlog.'
                )}
              </p>
            </div>
          </CardContent>
          {sweepRunning && sweep.data.total > 0 ? (
            <div className="h-1 w-full bg-slate-800">
              <div
                className="h-full bg-violet-500 transition-all duration-500"
                style={{
                  width: `${Math.min(
                    100,
                    Math.round((sweep.data.scanned / sweep.data.total) * 100),
                  )}%`,
                }}
              />
            </div>
          ) : null}
        </Card>
      ) : null}

      {isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="space-y-3 p-6">
            <p className="text-sm text-red-300">Unable to load upload jobs.</p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="space-y-3">
        {items.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            retryPending={retry.isPending}
            onRetry={(id) =>
              retry.mutate(id, {
                onSuccess: () => toast({ title: 'Upload job retried' }),
                onError: (err: unknown) => {
                  const axiosError = err as {
                    response?: { data?: { error?: { message?: string } } };
                  };
                  toast({
                    title:
                      axiosError.response?.data?.error?.message ?? 'Retry failed',
                    variant: 'destructive',
                  });
                },
              })
            }
          />
        ))}
        {!isLoading && !isError && items.length === 0 ? (
          <Card className="border-slate-800 bg-slate-900/50">
            <CardContent className="p-6 text-sm text-slate-400">No upload jobs found.</CardContent>
          </Card>
        ) : null}
      </div>

      <Pagination
        page={page}
        pageSize={pageSize}
        totalCount={total}
        onPageChange={(nextPage) => setPage(nextPage)}
      />
    </div>
  );
}
