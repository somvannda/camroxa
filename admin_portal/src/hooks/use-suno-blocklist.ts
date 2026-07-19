import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  CreateSunoBlocklistRequest,
  PromoteSunoBlocklistRequest,
  SunoBlocklistListResponse,
  SunoBlocklistTerm,
  SunoFailureMetricsResponse,
  UpdateSunoBlocklistRequest,
} from '@/types/suno-blocklist';

const sunoBlocklistKeys = {
  all: ['suno-blocklist'] as const,
  list: () => ['suno-blocklist', 'list'] as const,
};

export function useSunoBlocklist() {
  return useQuery({
    queryKey: sunoBlocklistKeys.list(),
    queryFn: () => httpClient.get<SunoBlocklistListResponse>('/api/v1/admin/suno-blocklist'),
  });
}

export function useCreateSunoBlocklistTerm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateSunoBlocklistRequest) =>
      httpClient.post<SunoBlocklistTerm>('/api/v1/admin/suno-blocklist', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sunoBlocklistKeys.all });
    },
  });
}

export function useUpdateSunoBlocklistTerm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateSunoBlocklistRequest }) =>
      httpClient.put<SunoBlocklistTerm>(`/api/v1/admin/suno-blocklist/${encodeURIComponent(id)}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sunoBlocklistKeys.all });
    },
  });
}

export function useDeleteSunoBlocklistTerm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete<void>(`/api/v1/admin/suno-blocklist/${encodeURIComponent(id)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sunoBlocklistKeys.all });
    },
  });
}

export function usePromoteSunoBlocklistTerm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PromoteSunoBlocklistRequest) =>
      httpClient.post<SunoBlocklistTerm>('/api/v1/admin/suno-blocklist/promote', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sunoBlocklistKeys.all });
    },
  });
}

export function useSunoFailureMetrics(days = 30) {
  return useQuery({
    queryKey: ['suno-blocklist', 'failure-metrics', days] as const,
    queryFn: () =>
      httpClient.get<SunoFailureMetricsResponse>(
        `/api/v1/admin/suno-blocklist/failure-metrics?days=${days}`,
      ),
  });
}
