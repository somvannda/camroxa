import { useQuery } from '@tanstack/react-query';
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
      'Invalid health payload — expected Platform API JSON from /api/v1/health (not admin SPA HTML).',
    );
  }
  return data as HealthStatus;
}

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health'],
    // Same-origin /api/ is proxied to platform_api. Do NOT call /health on the
    // admin host — nginx serves index.html there (false "Unknown" / unreachable).
    queryFn: async () => assertHealthPayload(await httpClient.get<HealthStatus>('/api/v1/health')),
    refetchInterval: 30_000, // Poll health every 30s
  });
}

export function useSunoBalance() {
  return useQuery({
    queryKey: ['suno-balance'],
    queryFn: () =>
      httpClient.get<{ credits: number | null; status: string }>('/api/v1/admin/suno-balance'),
  });
}

export function useProviderKeyBalances() {
  return useQuery({
    queryKey: ['provider-key-balances'],
    queryFn: () =>
      httpClient.get<ProviderKeyBalancesResponse>(
        '/api/v1/admin/provider-key-balances?refresh=true',
      ),
    refetchOnWindowFocus: true,
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
    queryFn: () => httpClient.get<AdminOverview>('/api/v1/admin/overview'),
  });
}
