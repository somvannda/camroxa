import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { UpdateRateLimitRequest, UpdateSlaiImageProviderConfigRequest } from '@/types/api';
import type { RateLimitConfig, SlaiImageProviderConfig } from '@/types/models';

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

export function useSlaiImageProviderConfig() {
  return useQuery({
    queryKey: ['rate-limits', 'slai-image-provider'],
    queryFn: async () => {
      const response = await httpClient.get<SlaiImageProviderConfig>(
        '/api/v1/admin/rate-limits/slai-image-provider',
      );
      return response;
    },
  });
}

export function useUpdateSlaiImageProviderConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateSlaiImageProviderConfigRequest) =>
      httpClient.put<SlaiImageProviderConfig>(
        '/api/v1/admin/rate-limits/slai-image-provider',
        data,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rate-limits', 'slai-image-provider'] });
    },
  });
}
