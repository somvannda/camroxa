import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { UpdateRateLimitRequest } from '@/types/api';
import type { RateLimitConfig } from '@/types/models';

export function useRateLimits() {
  return useQuery({
    queryKey: ['rate-limits'],
    queryFn: async () => {
      const response = await httpClient.get<{ configs: RateLimitConfig[] }>('/api/v1/admin/rate-limits');
      return response.configs;
    },
  });
}

export function useUpdateRateLimit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateRateLimitRequest) =>
      httpClient.put<RateLimitConfig>('/api/v1/admin/rate-limits', data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['rate-limits'] }),
  });
}
