import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

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
import { useRetryFailedUploadJobs, useRetryUploadJob, useStreamingUploadJobs } from '@/hooks/use-streaming';
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
            {job.permanent_failed ? (
              <Badge variant="destructive">permanent</Badge>
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

        {job.status === 'failed' && !job.permanent_failed && String(job.kind).startsWith('mp3_') ? (
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

export default function StreamingUploadJobsPage() {
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'pending' | 'running' | 'success' | 'failed'
  >('all');
  const [kindFilter, setKindFilter] = useState<'all' | 'mp3_ok' | 'mp3_alt' | 'cover'>('all');
  const [q, setQ] = useState('');
  const { data, isLoading, isError, refetch } = useStreamingUploadJobs(
    statusFilter === 'all' ? undefined : statusFilter,
  );
  const retry = useRetryUploadJob();
  const retryFailed = useRetryFailedUploadJobs();

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? []).filter((job) => {
      if (kindFilter !== 'all' && job.kind !== kindFilter) return false;
      if (!needle) return true;
      const hay = [
        job.id,
        job.kind,
        job.status,
        job.user_email,
        job.user_display_name,
        job.song_title,
        job.song_album,
        job.stream_album_name,
        job.batch_id,
        job.song_id,
        job.storage_key,
        job.error,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [data, kindFilter, q]);

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
            <Button variant="outline" onClick={() => refetch()}>
              Refresh
            </Button>
            <Button
              variant="outline"
              disabled={retryFailed.isPending}
              onClick={() =>
                retryFailed.mutate(
                  { limit: 50, maxAgeHours: 72 },
                  {
                    onSuccess: (res) =>
                      toast({
                        title: `Retried ${res.retried} job(s): ${res.succeeded} ok, ${res.failed} failed`,
                      }),
                    onError: () =>
                      toast({ title: 'Bulk retry failed', variant: 'destructive' }),
                  },
                )
              }
            >
              {retryFailed.isPending ? 'Retrying…' : 'Retry failed (72h)'}
            </Button>
          </div>
        }
      />

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

      <div className="text-xs text-slate-500">
        Showing {filtered.length} of {(data ?? []).length} loaded jobs
      </div>

      <div className="space-y-3">
        {filtered.map((job) => (
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
        {!isLoading && !isError && filtered.length === 0 ? (
          <Card className="border-slate-800 bg-slate-900/50">
            <CardContent className="p-6 text-sm text-slate-400">No upload jobs found.</CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
