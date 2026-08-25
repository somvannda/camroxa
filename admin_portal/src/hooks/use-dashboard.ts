import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { HealthStatus } from '@/types/models';
import type { ProviderKeyBalancesResponse } from '@/types/provider-balances';

function assertHealthPayload(data: unknown): HealthStatus {
  if (
    data == null ||
    typeof data !== 'object' ||
    typeof (data as HealthStatus).status !== 'string'
  ) {
    throw new Error(
      'Invalid health payload — expected Platform API JSON from /api/v3/health (not admin SPA HTML).',
    );
  }
  return data as HealthStatus;
}

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health'],
    // Same-origin /api/ is proxied to platform_api. Do NOT call /health on the
    // admin host — nginx serves index.html there (false "Unknown" / unreachable).
    queryFn: async () => assertHealthPayload(await httpClient.get<HealthStatus>('/api/v3/health')),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  });
}

export function useSunoBalance() {
  return useQuery({
    queryKey: ['suno-balance'],
    queryFn: () =>
      httpClient.get<{ credits: number | null; status: string }>('/api/v3/admin/suno-balance'),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useProviderKeyBalances() {
  return useQuery({
    queryKey: ['provider-key-balances'],
    queryFn: () =>
      httpClient.get<ProviderKeyBalancesResponse>(
        '/api/v3/admin/provider-key-balances?refresh=false',
      ),
    refetchInterval: 20_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}

export function useForceRefreshProviderKeyBalances() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.get<ProviderKeyBalancesResponse>(
        '/api/v3/admin/provider-key-balances?refresh=true',
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(['provider-key-balances'], data);
    },
  });
}

export interface AdminOverview {
  total_users: number;
  total_admins: number;
  active_users: number;
  suspended_users: number;
  deleted_users: number;
  new_users_7d: number;
  new_users_30d: number;
  users_with_profiles: number;
  users_with_active_license: number;
  active_licenses: number;
  total_songs: number;
  total_images: number;
}

export function useAdminOverview() {
  return useQuery({
    queryKey: ['admin-overview'],
    queryFn: () => httpClient.get<AdminOverview>('/api/v3/admin/overview'),
  });
}
