import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { HealthStatus } from '@/types/models';

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => httpClient.get<HealthStatus>('/health'),
    refetchInterval: 30_000, // Poll health every 30s
  });
}

export function useSunoBalance() {
  return useQuery({
    queryKey: ['suno-balance'],
    queryFn: () => httpClient.get<{ balance: number }>('/api/v1/admin/suno-balance'),
  });
}
