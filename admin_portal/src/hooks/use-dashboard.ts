import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { HealthStatus } from '@/types/models';
import type { ProviderKeyBalancesResponse } from '@/types/provider-balances';

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
