import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { UsageListParams } from '@/types/api';
import type { UsageFiltersResponse, UsageListResponse } from '@/types/models';

export function useUsage(params: UsageListParams) {
  return useQuery({
    queryKey: ['usage', params],
    queryFn: () =>
      httpClient.get<UsageListResponse>(
        '/api/v1/admin/usage',
        params as Record<string, unknown>,
      ),
  });
}

export function useUsageFilters() {
  return useQuery({
    queryKey: ['usage-filters'],
    queryFn: () => httpClient.get<UsageFiltersResponse>('/api/v1/admin/usage/filters'),
    staleTime: 60_000,
  });
}
