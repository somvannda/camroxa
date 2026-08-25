import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  AdminPipelineBatchDetail,
  AdminPipelineBoardResponse,
  AdminPipelineRetryCosts,
  PipelineBoardParams,
} from '@/types/pipeline';

export const pipelineKeys = {
  all: ['admin-pipeline'] as const,
  board: (params: PipelineBoardParams) => ['admin-pipeline', 'board', params] as const,
  batch: (batchId: string) => ['admin-pipeline', 'batch', batchId] as const,
  retryCosts: ['admin-pipeline', 'retry-costs'] as const,
};

export function usePipelineBoard(params: PipelineBoardParams, enabled = true) {
  return useQuery({
    queryKey: pipelineKeys.board(params),
    enabled,
    refetchInterval: (query) => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return false;
      }
      // P4.6: WS push invalidates; keep a slow safety poll.
      return query.state.error ? false : 60_000;
    },
    refetchIntervalInBackground: false,
    queryFn: () => {
      const query: Record<string, unknown> = {
        limit: params.limit ?? 50,
        active_only: params.active_only ?? true,
      };
      if (params.stage && params.stage !== 'all') query.stage = params.stage;
      if (params.user_id) query.user_id = params.user_id;
      if (params.q) query.q = params.q;
      return httpClient.get<AdminPipelineBoardResponse>(
        '/api/v3/admin/pipeline/board',
        query,
      );
    },
  });
}

export function usePipelineBatchDetail(batchId: string | null) {
  return useQuery({
    queryKey: pipelineKeys.batch(batchId || ''),
    enabled: Boolean(batchId),
    queryFn: () =>
      httpClient.get<AdminPipelineBatchDetail>(
        `/api/v3/admin/pipeline/batches/${batchId}`,
      ),
  });
}

export function usePipelineRetryCosts(enabled = true) {
  return useQuery({
    queryKey: pipelineKeys.retryCosts,
    enabled,
    staleTime: 60_000,
    queryFn: () =>
      httpClient.get<AdminPipelineRetryCosts>('/api/v3/admin/pipeline/retry-costs'),
  });
}

function invalidatePipeline(queryClient: ReturnType<typeof useQueryClient>, batchId: string) {
  void queryClient.invalidateQueries({ queryKey: pipelineKeys.all });
  void queryClient.invalidateQueries({ queryKey: pipelineKeys.batch(batchId) });
}

export function useAdminRetryDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      batchId,
      songId,
      waiveBilling,
      reason,
    }: {
      batchId: string;
      songId: string;
      waiveBilling?: boolean;
      reason?: string;
    }) =>
      httpClient.post(
        `/api/v3/admin/pipeline/batches/${batchId}/songs/${songId}/retry-draft`,
        {
          waive_billing: Boolean(waiveBilling),
          reason: reason || null,
        },
      ),
    onSuccess: (_data, vars) => invalidatePipeline(queryClient, vars.batchId),
  });
}

export function useAdminRetrySuno() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      batchId,
      songId,
      waiveBilling,
      reason,
    }: {
      batchId: string;
      songId: string;
      waiveBilling?: boolean;
      reason?: string;
    }) =>
      httpClient.post(
        `/api/v3/admin/pipeline/batches/${batchId}/songs/${songId}/retry-suno`,
        {
          waive_billing: Boolean(waiveBilling),
          reason: reason || null,
        },
      ),
    onSuccess: (_data, vars) => invalidatePipeline(queryClient, vars.batchId),
  });
}

export function useAdminRetryImages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      batchId,
      jobIds,
      channelRole,
      waiveBilling,
      reason,
    }: {
      batchId: string;
      jobIds?: string[];
      channelRole?: string;
      waiveBilling?: boolean;
      reason?: string;
    }) =>
      httpClient.post(`/api/v3/admin/pipeline/batches/${batchId}/retry-images`, {
        job_ids: jobIds,
        channel_role: channelRole,
        waive_billing: Boolean(waiveBilling),
        reason: reason || null,
      }),
    onSuccess: (_data, vars) => invalidatePipeline(queryClient, vars.batchId),
  });
}

export function useAdminRetryYoutube() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, jobId }: { batchId: string; jobId: string }) =>
      httpClient.post(
        `/api/v3/admin/pipeline/batches/${batchId}/youtube-jobs/${jobId}/retry`,
      ),
    onSuccess: (_data, vars) => invalidatePipeline(queryClient, vars.batchId),
  });
}
