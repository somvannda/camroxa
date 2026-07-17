import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { PaginatedResponse } from '@/types/api';
import type { ClientLogBatchSummary, ClientLogDetail } from '@/types/models';

export interface ClientLogListParams {
  page?: number;
  page_size?: number;
}

export function useUserClientLogs(userId: string, params: ClientLogListParams) {
  return useQuery({
    queryKey: ['client-logs', userId, params],
    enabled: Boolean(userId),
    queryFn: () =>
      httpClient.get<PaginatedResponse<ClientLogBatchSummary>>(
        `/api/v1/admin/users/${userId}/client-logs`,
        params as Record<string, unknown>,
      ),
  });
}

export function useClientLogBatch(batchId: string | null) {
  return useQuery({
    queryKey: ['client-log-batch', batchId],
    enabled: Boolean(batchId),
    queryFn: () =>
      httpClient.get<ClientLogDetail>(`/api/v1/admin/client-logs/${batchId}`),
  });
}
