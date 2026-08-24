import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, RefreshCw, X } from 'lucide-react';

import { ErrorState } from '@/components/shared/error-state';
import { PageHeader } from '@/components/shared/page-header';
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
  pipelineKeys,
  useAdminRetryDraft,
  useAdminRetryImages,
  useAdminRetrySuno,
  useAdminRetryYoutube,
  usePipelineBatchDetail,
  usePipelineBoard,
  usePipelineRetryCosts,
} from '@/hooks/use-pipeline-ops';
import { useRetryUploadJob } from '@/hooks/use-streaming';
import { useToast } from '@/hooks/use-toast';
import type {
  AdminPipelineBoardRow,
  AdminPipelineRetryCosts,
  AdminPipelineStreamingJob,
} from '@/types/pipeline';
import { cn } from '@/lib/utils';
import { useQueryClient } from '@tanstack/react-query';

const STAGE_OPTIONS = [
  'all',
  'Music',
  'Image',
  'Converter',
  'Export',
  'Merge',
  'YouTube',
  'Streaming',
  'Error',
  'Done',
  'Completed',
] as const;

function formatAge(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function stageTone(stage: string, status: string): string {
  const s = stage.toLowerCase();
  const st = status.toLowerCase();
  if (s === 'error' || st === 'failed') return 'bg-red-500/15 text-red-300 border-red-500/20';
  if (s === 'done' || s === 'completed') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20';
  if (s === 'streaming') return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/20';
  if (s === 'youtube') return 'bg-sky-500/15 text-sky-300 border-sky-500/20';
  if (s === 'image') return 'bg-violet-500/15 text-violet-300 border-violet-500/20';
  if (s === 'converter' || s === 'export' || s === 'merge' || s === 'merger') {
    return 'bg-amber-500/15 text-amber-300 border-amber-500/20';
  }
  return 'bg-slate-500/15 text-slate-300 border-slate-500/20';
}

function desktopStepState(
  done: boolean,
  active: boolean,
  isError: boolean,
): 'done' | 'active' | 'todo' {
  if (isError) return 'todo';
  if (done) return 'done';
  if (active) return 'active';
  return 'todo';
}

function ProgressStrip({ row }: { row: AdminPipelineBoardRow }) {
  const stageL = row.stage.toLowerCase();
  const isError = stageL === 'error';
  const converterL = (row.converter || '').toLowerCase();
  const mergeL = (row.merge || '').toLowerCase();

  const pastMusic = stageL !== 'music';
  const pastImage = !['music', 'image'].includes(stageL);
  const exportDone =
    converterL.includes('completed') ||
    ['merge', 'merger', 'youtube', 'streaming', 'done', 'completed'].includes(stageL);
  const exportActive =
    !exportDone &&
    (converterL.includes('progress') ||
      converterL === 'queued' ||
      stageL === 'converter' ||
      stageL === 'export');
  const mergeDone =
    mergeL.includes('completed') ||
    ['youtube', 'streaming', 'done', 'completed'].includes(stageL);
  const mergeActive =
    !mergeDone && (mergeL.includes('progress') || stageL === 'merge' || stageL === 'merger');
  const ytDone = ['streaming', 'done', 'completed'].includes(stageL);
  const ytActive = stageL === 'youtube';
  const streamDone = ['done', 'completed'].includes(stageL);
  const streamActive = stageL === 'streaming';

  const steps: Array<{ key: string; state: 'done' | 'active' | 'todo'; detail: string }> = [
    {
      key: 'Music',
      state: desktopStepState(pastMusic, stageL === 'music', isError),
      detail: row.music,
    },
    {
      key: 'Image',
      state: desktopStepState(pastImage, stageL === 'image', isError),
      detail: row.image,
    },
    {
      key: 'Export',
      state: desktopStepState(exportDone, exportActive, isError),
      detail: row.converter,
    },
    {
      key: 'Merge',
      state: desktopStepState(mergeDone, mergeActive, isError),
      detail: row.merge,
    },
    {
      key: 'YT',
      state: desktopStepState(ytDone, ytActive, isError),
      detail: row.youtube,
    },
    {
      key: 'Stream',
      state: desktopStepState(streamDone, streamActive, isError),
      detail: row.streaming || '—',
    },
  ];

  return (
    <div
      className="flex items-center gap-1"
      title={steps.map((s) => `${s.key}: ${s.detail}`).join(' · ')}
    >
      {steps.map((step) => (
        <div
          key={step.key}
          className={cn(
            'h-1.5 w-4 rounded-full',
            isError
              ? 'bg-red-400'
              : step.state === 'done'
                ? 'bg-violet-400'
                : step.state === 'active'
                  ? 'bg-amber-400'
                  : 'bg-slate-700',
          )}
          title={`${step.key}: ${step.detail}`}
        />
      ))}
    </div>
  );
}

function formatCredits(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(value)) return null;
  const rounded = Math.round(value * 10000) / 10000;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

function formatDraftCostLine(costs?: AdminPipelineRetryCosts | null): string {
  const min = formatCredits(costs?.draft_credits_min);
  const max = formatCredits(costs?.draft_credits_max);
  if (min && max && min !== max) {
    return `Estimated ~${min}–${max} credits (lyric ± title ± album), from the owner wallet.`;
  }
  if (min) {
    return `Estimated ~${min} credits (draft), from the owner wallet.`;
  }
  return 'Estimated cost unavailable — still charges the owner wallet in credits.';
}

function formatSunoCostLine(costs?: AdminPipelineRetryCosts | null): string {
  const amount = formatCredits(costs?.suno_credits);
  if (amount) {
    return `Estimated ~${amount} credits (1 music package: Primary + Secondary), from the owner wallet.`;
  }
  return 'Estimated cost unavailable — still charges the owner wallet in credits.';
}

function formatImageCostLine(
  jobs: Array<{ kind: string }>,
  costs?: AdminPipelineRetryCosts | null,
): string {
  if (!jobs.length) {
    return 'Estimated cost unavailable — still charges the owner wallet in credits.';
  }
  let total = 0;
  let known = 0;
  for (const job of jobs) {
    const kind = (job.kind || '').toLowerCase();
    const rate = kind.includes('thumb')
      ? costs?.thumbnail_image_credits
      : costs?.background_image_credits;
    if (rate != null && !Number.isNaN(rate)) {
      total += rate;
      known += 1;
    }
  }
  const amount = formatCredits(total);
  if (amount && known === jobs.length) {
    return `Estimated ~${amount} credits (${jobs.length} image job${jobs.length === 1 ? '' : 's'}), from the owner wallet.`;
  }
  if (amount && known > 0) {
    return `Estimated at least ~${amount} credits for ${known}/${jobs.length} priced jobs, from the owner wallet.`;
  }
  return `Estimated cost unavailable for ${jobs.length} image job(s) — still charges the owner wallet in credits.`;
}

function confirmOwnerCharge(
  action: string,
  userEmail: string,
  costLine?: string,
): boolean {
  const estimate = costLine ? `\n${costLine}\n` : '\n';
  return window.confirm(
    `${action}\n\nThis charges ${userEmail}'s credits wallet the same as if they retried themselves.${estimate}\nContinue?`,
  );
}

function confirmStreamingRetry(kind: string): boolean {
  return window.confirm(
    `Retry streaming upload (${kind})?\n\nThis re-uploads to the music catalog storage. It does not charge generation credits.`,
  );
}

function confirmYoutubeRetry(role: string | null): boolean {
  return window.confirm(
    `Requeue YouTube upload${role ? ` (${role})` : ''}?\n\nNo credit charge. The upload worker still needs access to the merged MP4 (usually via the owner's desktop run).`,
  );
}

function formatWhen(value?: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function matchesStreamingRole(job: AdminPipelineStreamingJob, role: string): boolean {
  const kind = (job.kind || '').toLowerCase();
  const roleKey = role.toUpperCase();
  if (kind === 'cover') {
    const channel = (job.stream_channel_role || '').toLowerCase();
    if (!channel) return true;
    return roleKey === 'ALT' ? channel === 'alt' : channel === 'ok';
  }
  if (roleKey === 'ALT') return kind === 'mp3_alt';
  return kind === 'mp3_ok';
}

function canRetryDraft(status: string): boolean {
  const s = status.toLowerCase();
  return s === 'draft_failed' || s === 'pending';
}

function canRetrySuno(status: string, sunoStatus: string | null): boolean {
  const s = status.toLowerCase();
  if (s === 'draft_ready' || s === 'suno_failed') return true;
  if (s === 'suno_pending' && (sunoStatus || '').toLowerCase() === 'failed') return true;
  return false;
}

function PipelineDrawer({
  row,
  onClose,
}: {
  row: AdminPipelineBoardRow | null;
  onClose: () => void;
}) {
  const { data, isLoading, isError, refetch } = usePipelineBatchDetail(row?.batch_id ?? null);
  const { data: retryCosts } = usePipelineRetryCosts(Boolean(row));
  const [waiveBilling, setWaiveBilling] = useState(false);
  const [waiveReason, setWaiveReason] = useState('');
  const retryDraft = useAdminRetryDraft();
  const retrySuno = useAdminRetrySuno();
  const retryImages = useAdminRetryImages();
  const retryYoutube = useAdminRetryYoutube();
  const retryStreaming = useRetryUploadJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const busy =
    retryDraft.isPending ||
    retrySuno.isPending ||
    retryImages.isPending ||
    retryYoutube.isPending ||
    retryStreaming.isPending;

  if (!row) return null;

  const allStreaming = data?.streaming_jobs ?? [];
  const streamingForRole = allStreaming.filter((job) => matchesStreamingRole(job, row.role));
  const streamingOther = allStreaming.filter((job) => !matchesStreamingRole(job, row.role));
  const failedImagesForRole = (data?.image_jobs ?? []).filter(
    (job) =>
      job.status.toLowerCase() === 'failed' &&
      (job.channel_role || '').toUpperCase() === row.role.toUpperCase(),
  );

  const billingOpts = () => ({
    waiveBilling,
    reason: waiveBilling ? waiveReason.trim() : undefined,
  });

  const runRetry = async (
    label: string,
    action: () => Promise<unknown>,
    costLine?: string,
  ) => {
    if (waiveBilling && waiveReason.trim().length < 8) {
      toast({
        title: 'Waive reason required',
        description: 'Enter at least 8 characters explaining why this is platform-paid.',
        variant: 'destructive',
      });
      return;
    }
    if (waiveBilling) {
      const ok = window.confirm(
        `${label}\n\nPLATFORM-PAID: ${row.user_email} will NOT be charged.\nReason: ${waiveReason.trim()}\n${costLine ? `COGS estimate: ${costLine}\n` : ''}\nContinue?`,
      );
      if (!ok) return;
    } else if (!confirmOwnerCharge(label, row.user_email, costLine)) {
      return;
    }
    try {
      const result = (await action()) as { requires_approval?: boolean; message?: string } | undefined;
      if (result?.requires_approval) {
        toast({
          title: 'Queued for dual-control',
          description: result.message || 'A second admin must approve this platform-paid retry on Credits → Pending ops.',
        });
      } else {
        toast({
          title: `${label} queued`,
          description: waiveBilling
            ? `Platform-paid (no charge to ${row.user_email})`
            : `Charged to ${row.user_email}`,
        });
      }
      await refetch();
    } catch {
      // Global MutationCache already shows the error toast.
    }
  };

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-xl flex-col border-l border-slate-800 bg-slate-950 shadow-2xl">
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-5 py-4">
        <div className="min-w-0 space-y-1">
          <div className="text-xs uppercase tracking-wide text-slate-500">Pipeline detail</div>
          <h2 className="truncate text-lg font-semibold text-slate-100">
            {row.album || 'Untitled album'}
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <Badge className={cn('border', stageTone(row.stage, row.status))}>
              {row.stage} · {row.status}
            </Badge>
            <Badge variant="outline" className="border-slate-700 text-slate-300">
              {row.role}
            </Badge>
            <span>{row.profile_name}</span>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="text-slate-400">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="space-y-2 p-4 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">User</span>
              <Link to={`/users/${row.user_id}`} className="text-blue-400 hover:underline">
                {row.user_display_name || row.user_email}
              </Link>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Email</span>
              <span className="text-slate-200">{row.user_email}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Batch</span>
              <Link
                to={`/batches/${row.batch_id}`}
                className="font-mono text-xs text-blue-400 hover:underline"
              >
                {row.batch_id.slice(0, 8)}…
              </Link>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Age in stage</span>
              <span className="text-slate-200">{formatAge(row.age_seconds)}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Updated</span>
              <span className="text-slate-200">{row.updated}</span>
            </div>
            {row.error_snippet ? (
              <div className="rounded-md border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200">
                {row.error_snippet}
              </div>
            ) : (
              <p className="text-xs text-slate-400">{row.notes}</p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Button asChild size="sm" variant="outline">
                <Link to={`/usage?user_id=${row.user_id}`}>Usage</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to={`/client-logs?user_id=${row.user_id}`}>Client logs</Link>
              </Button>
              {failedImagesForRole.length > 0 ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runRetry(
                      `Retry ${failedImagesForRole.length} failed image(s) (${row.role})`,
                      () =>
                        retryImages.mutateAsync({
                          batchId: row.batch_id,
                          channelRole: row.role,
                          ...billingOpts(),
                        }),
                      formatImageCostLine(failedImagesForRole, retryCosts),
                    )
                  }
                >
                  Retry failed images
                </Button>
              ) : null}
            </div>
            <p className="pt-1 text-[11px] text-amber-200/80">
              Retries charge this user&apos;s credits wallet (same path as desktop) unless
              platform-paid waive is enabled below. Confirm dialogs include estimated credit cost
              when pricing is available.
            </p>
            <label className="mt-2 flex items-start gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={waiveBilling}
                onChange={(e) => setWaiveBilling(e.target.checked)}
              />
              <span>
                Platform-paid support retry (waive owner charge). Requires a reason. Admin wallet is
                never charged.
              </span>
            </label>
            {waiveBilling ? (
              <Input
                className="mt-2 h-9 border-slate-700 bg-slate-950 text-xs"
                placeholder="Waive reason (min 8 chars)…"
                value={waiveReason}
                onChange={(e) => setWaiveReason(e.target.value)}
              />
            ) : null}
          </CardContent>
        </Card>

        {isLoading ? <Skeleton className="h-40 w-full" /> : null}
        {isError ? (
          <ErrorState message="Failed to load batch detail" onRetry={() => refetch()} />
        ) : null}

        {data ? (
          <>
            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">Desktop export</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">Converter / Export</span>
                  <span className="text-right text-slate-200">{row.converter || '—'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">Merge</span>
                  <span className="text-right text-slate-200">{row.merge || '—'}</span>
                </div>
                <p className="pt-1 text-[11px] text-slate-500">
                  Runs on the owner&apos;s desktop. Status is inferred when the API cannot see the
                  local run folder (In progress / Completed). No admin retry for these steps.
                </p>
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">
                  Songs ({data.songs.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0">
                {data.songs.map((song) => (
                  <div
                    key={song.id}
                    className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-slate-200">
                          #{song.batch_index + 1} {song.title || 'Untitled'}
                        </div>
                        <div className="mt-1 text-slate-500">
                          song {song.status}
                          {song.suno_status ? ` · suno ${song.suno_status}` : ''}
                        </div>
                      </div>
                      <Link
                        to={`/songs/${song.id}`}
                        className="shrink-0 text-blue-400 hover:underline"
                      >
                        open
                      </Link>
                    </div>
                    {song.suno_error ? (
                      <p className="mt-2 text-red-300">{song.suno_error}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {canRetryDraft(song.status) ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() =>
                            void runRetry(
                              `Retry draft for “${song.title || song.id.slice(0, 8)}”`,
                              () =>
                                retryDraft.mutateAsync({
                                  batchId: row.batch_id,
                                  songId: song.id,
                                  ...billingOpts(),
                                }),
                              formatDraftCostLine(retryCosts),
                            )
                          }
                        >
                          Retry draft
                        </Button>
                      ) : null}
                      {canRetrySuno(song.status, song.suno_status) ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() =>
                            void runRetry(
                              `Retry Suno for “${song.title || song.id.slice(0, 8)}”`,
                              () =>
                                retrySuno.mutateAsync({
                                  batchId: row.batch_id,
                                  songId: song.id,
                                  ...billingOpts(),
                                }),
                              formatSunoCostLine(retryCosts),
                            )
                          }
                        >
                          Retry Suno
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">
                  Image jobs ({data.image_jobs.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0">
                {data.image_jobs.length === 0 ? (
                  <p className="text-xs text-slate-500">No image jobs yet.</p>
                ) : (
                  data.image_jobs.map((job) => (
                    <div
                      key={job.id}
                      className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs"
                    >
                      <div className="flex justify-between gap-2 text-slate-200">
                        <span>
                          {job.channel_role || '—'} · {job.kind}
                          {job.provider ? ` · ${job.provider}` : ''}
                        </span>
                        <span>
                          {job.status}
                          {job.attempt_count > 1 ? ` ×${job.attempt_count}` : ''}
                        </span>
                      </div>
                      {typeof job.prompt_length === 'number' ? (
                        <p className="mt-1 text-slate-500">
                          Prompt length: {job.prompt_length}
                          {job.prompt_length > 5000 ? ' (over 5000 max)' : ''}
                        </p>
                      ) : null}
                      {job.error ? <p className="mt-2 text-red-300">{job.error}</p> : null}
                      {job.status.toLowerCase() === 'failed' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2"
                          disabled={busy}
                          onClick={() =>
                            void runRetry(
                              `Retry image ${job.channel_role || ''} ${job.kind}`,
                              () =>
                                retryImages.mutateAsync({
                                  batchId: row.batch_id,
                                  jobIds: [job.id],
                                  ...billingOpts(),
                                }),
                              formatImageCostLine([job], retryCosts),
                            )
                          }
                        >
                          Retry image
                        </Button>
                      ) : null}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">
                  YouTube ({data.youtube_jobs.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0">
                {data.youtube_jobs.length === 0 ? (
                  <p className="text-xs text-slate-500">No YouTube jobs yet.</p>
                ) : (
                  data.youtube_jobs.map((job) => {
                    const canRetry = ['failed', 'blocked', 'cancelled'].includes(
                      job.status.toLowerCase(),
                    );
                    return (
                      <div
                        key={job.id}
                        className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs"
                      >
                        <div className="flex justify-between gap-2 text-slate-200">
                          <span>{job.role || '—'}</span>
                          <span>{job.status}</span>
                        </div>
                        {job.updated_at ? (
                          <div className="mt-1 text-slate-500">
                            Updated {formatWhen(job.updated_at)}
                          </div>
                        ) : null}
                        {job.youtube_url ? (
                          <a
                            href={job.youtube_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-block text-blue-400 hover:underline"
                          >
                            Open video
                          </a>
                        ) : null}
                        {job.error_message ? (
                          <p className="mt-2 text-red-300">{job.error_message}</p>
                        ) : null}
                        {canRetry ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="mt-2"
                            disabled={busy}
                            onClick={() => {
                              if (!confirmYoutubeRetry(job.role)) return;
                              void (async () => {
                                try {
                                  await retryYoutube.mutateAsync({
                                    batchId: row.batch_id,
                                    jobId: job.id,
                                  });
                                  toast({ title: 'YouTube job requeued' });
                                  await refetch();
                                } catch {
                                  // Global MutationCache already toasted.
                                }
                              })();
                            }}
                          >
                            Retry YouTube
                          </Button>
                        ) : null}
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-sm text-slate-100">
                  <span>
                    Streaming ({streamingForRole.length}
                    {allStreaming.length ? ` / ${allStreaming.length} batch` : ''})
                  </span>
                  <Button asChild size="sm" variant="ghost" className="h-7 text-xs">
                    <Link to="/streaming/upload-jobs">All jobs</Link>
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0">
                <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs text-slate-400">
                  Channel progress: {row.streaming || '—'} · showing {row.role} jobs first
                </div>
                {streamingForRole.length === 0 && streamingOther.length === 0 ? (
                  <p className="text-xs text-slate-500">
                    No streaming upload jobs for this batch yet (uploads start after Suno).
                  </p>
                ) : null}
                {[...streamingForRole, ...streamingOther].map((job) => {
                  const forRole = matchesStreamingRole(job, row.role);
                  const title =
                    job.song_title ||
                    (job.song_batch_index != null
                      ? `Track #${job.song_batch_index + 1}`
                      : null) ||
                    job.stream_album_name ||
                    job.kind;
                  return (
                    <div
                      key={job.id}
                      className={cn(
                        'rounded-md border bg-slate-950/60 p-3 text-xs',
                        forRole ? 'border-cyan-500/20' : 'border-slate-800 opacity-70',
                      )}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 text-slate-200">
                        <span className="font-medium">{title}</span>
                        <span>
                          {job.kind} · {job.status}
                          {job.attempt_count > 1 ? ` ×${job.attempt_count}` : ''}
                        </span>
                      </div>
                      <div className="mt-1 grid gap-0.5 text-slate-500 sm:grid-cols-2">
                        <div>
                          Album: {job.stream_album_name || job.song_album || '—'}
                          {job.stream_channel_role ? ` · ${job.stream_channel_role}` : ''}
                        </div>
                        <div>
                          Publish:{' '}
                          {job.stream_track_publish_status ||
                            job.stream_album_publish_status ||
                            '—'}
                        </div>
                        <div>Created: {formatWhen(job.created_at)}</div>
                        <div>Updated: {formatWhen(job.updated_at)}</div>
                      </div>
                      {job.song_id ? (
                        <Link
                          to={`/songs/${job.song_id}`}
                          className="mt-1 inline-block text-blue-400 hover:underline"
                        >
                          Open song
                        </Link>
                      ) : null}
                      {job.storage_key ? (
                        <p className="mt-1 break-all font-mono text-[10px] text-slate-600">
                          {job.storage_key}
                        </p>
                      ) : null}
                      {job.error ? <p className="mt-2 text-red-300">{job.error}</p> : null}
                      {job.status.toLowerCase() === 'failed' &&
                      (job.kind || '').toLowerCase().startsWith('mp3') ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2"
                          disabled={busy}
                          onClick={() => {
                            if (!confirmStreamingRetry(job.kind)) return;
                            void (async () => {
                              try {
                                await retryStreaming.mutateAsync(job.id);
                                toast({
                                  title: `Retry streaming ${job.kind} queued`,
                                });
                                void queryClient.invalidateQueries({
                                  queryKey: pipelineKeys.batch(row.batch_id),
                                });
                                void queryClient.invalidateQueries({
                                  queryKey: pipelineKeys.all,
                                });
                                await refetch();
                              } catch {
                                // Global MutationCache already toasted.
                              }
                            })();
                          }}
                        >
                          Retry upload
                        </Button>
                      ) : null}
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <p className="pb-6 text-[11px] text-slate-600">
              Stage order ends with Streaming (music catalog upload) before Done. Converter/Merge
              status is read-only — use Client logs if desktop export looks stuck.
            </p>
          </>
        ) : null}
      </div>
    </aside>
  );
}

export default function PipelineOpsPage() {
  const [activeOnly, setActiveOnly] = useState(true);
  const [stuckOnly, setStuckOnly] = useState(false);
  const [stage, setStage] = useState<string>('all');
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<AdminPipelineBoardRow | null>(null);

  const params = useMemo(
    () => ({
      limit: 50,
      active_only: activeOnly,
      stage: stage === 'all' ? undefined : stage,
      q: search || undefined,
    }),
    [activeOnly, stage, search],
  );

  const { data, isLoading, isError, isFetching, refetch } = usePipelineBoard(params);
  const counts = data?.counts;
  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    if (!stuckOnly) return all;
    return all.filter(
      (row) =>
        (row.age_seconds ?? 0) >= 15 * 60 &&
        !['Done', 'Completed'].includes(row.stage),
    );
  }, [data?.rows, stuckOnly]);

  return (
    <div className="relative space-y-6 p-6">
      <PageHeader
        title="Pipeline Ops"
        description="Live multi-user board — who is where, what failed, and how long they've been stuck."
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-slate-700 text-slate-400">
              <Activity className="mr-1.5 h-3.5 w-3.5" />
              Auto-refresh 10s
            </Badge>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', isFetching && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-4">
            <div className="text-xs text-slate-500">Active</div>
            <div className="mt-1 text-2xl font-semibold text-slate-100">{counts?.active ?? '—'}</div>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-4">
            <div className="text-xs text-slate-500">Failed</div>
            <div className="mt-1 text-2xl font-semibold text-red-300">{counts?.failed ?? '—'}</div>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-4">
            <div className="text-xs text-slate-500">Stuck ≥15m</div>
            <div className="mt-1 text-2xl font-semibold text-amber-300">{counts?.stuck ?? '—'}</div>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-4">
            <div className="text-xs text-slate-500">Showing</div>
            <div className="mt-1 text-2xl font-semibold text-slate-100">{counts?.total ?? '—'}</div>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3 md:flex-row md:items-center">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setSearch(q.trim());
          }}
          placeholder="Search email, name, or batch id…"
          className="md:max-w-sm"
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setSearch(q.trim())}
        >
          Search
        </Button>
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Stage" />
          </SelectTrigger>
          <SelectContent>
            {STAGE_OPTIONS.map((value) => (
              <SelectItem key={value} value={value}>
                {value === 'all' ? 'All stages' : value}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={activeOnly ? 'active' : 'all'}
          onValueChange={(value) => setActiveOnly(value === 'active')}
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Active only</SelectItem>
            <SelectItem value="all">Include Done</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={stuckOnly ? 'stuck' : 'any'}
          onValueChange={(value) => setStuckOnly(value === 'stuck')}
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">Any age</SelectItem>
            <SelectItem value="stuck">Stuck ≥15m</SelectItem>
          </SelectContent>
        </Select>
        <div className="text-xs text-slate-500 md:ml-auto">{data?.summary}</div>
      </div>

      {isLoading ? <Skeleton className="h-64 w-full" /> : null}
      {isError ? (
        <ErrorState message="Failed to load pipeline board" onRetry={() => refetch()} />
      ) : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardContent className="p-8 text-center text-sm text-slate-400">
            No active pipelines match these filters.
          </CardContent>
        </Card>
      ) : null}

      {!isLoading && !isError && rows.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-3 font-medium">User</th>
                  <th className="px-3 py-3 font-medium">Album / channel</th>
                  <th className="px-3 py-3 font-medium">Stage</th>
                  <th className="px-3 py-3 font-medium">Progress</th>
                  <th className="px-3 py-3 font-medium">Age</th>
                  <th className="px-3 py-3 font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                {rows.map((row) => {
                  const key = `${row.batch_id}:${row.role}`;
                  const selectedKey = selected
                    ? `${selected.batch_id}:${selected.role}`
                    : null;
                  const isSelected = key === selectedKey;
                  const isFailed =
                    row.stage === 'Error' || row.status.toLowerCase() === 'failed';
                  const isStuck =
                    (row.age_seconds ?? 0) >= 15 * 60 &&
                    !['Done', 'Completed'].includes(row.stage);
                  return (
                    <tr
                      key={key}
                      onClick={() => setSelected(row)}
                      className={cn(
                        'cursor-pointer transition-colors hover:bg-slate-900/70',
                        isSelected && 'bg-violet-500/10',
                        isFailed && 'bg-red-500/5',
                        isStuck && !isFailed && 'bg-amber-500/5',
                      )}
                    >
                      <td className="px-3 py-3 align-top">
                        <div className="font-medium text-slate-100">
                          {row.user_display_name || row.user_email}
                        </div>
                        <div className="text-xs text-slate-500">{row.user_email}</div>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="max-w-[220px] truncate text-slate-200">
                          {row.album || 'Untitled'}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                          <Badge variant="outline" className="border-slate-700 text-slate-300">
                            {row.role}
                          </Badge>
                          <span className="truncate">{row.profile_name}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <Badge className={cn('border', stageTone(row.stage, row.status))}>
                          {row.stage}
                        </Badge>
                        <div className="mt-1 text-xs text-slate-500">{row.status}</div>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <ProgressStrip row={row} />
                        <div className="mt-1 max-w-[220px] truncate text-[11px] text-slate-500">
                          {row.music} · Exp {row.converter} · Mrg {row.merge}
                        </div>
                      </td>
                      <td className="px-3 py-3 align-top text-slate-300">
                        {formatAge(row.age_seconds)}
                        <div className="text-[11px] text-slate-500">{row.updated}</div>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="max-w-[240px] truncate text-xs text-red-300">
                          {row.error_snippet || '—'}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {selected ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-black/40"
            aria-label="Close pipeline drawer"
            onClick={() => setSelected(null)}
          />
          <PipelineDrawer row={selected} onClose={() => setSelected(null)} />
        </>
      ) : null}
    </div>
  );
}
