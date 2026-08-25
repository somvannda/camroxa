import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type { V3Plan, V3PlanPatch, V3WalletView } from '@/types/v3-billing';

export function useV3Plans() {
  return useQuery({
    queryKey: ['v3-plans'],
    queryFn: () => httpClient.get<V3Plan[]>('/api/v3/admin/plans'),
  });
}

export function usePatchV3Plan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: V3PlanPatch }) =>
      httpClient.patch<V3Plan>(`/api/v3/admin/plans/${data.id}`, data.updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v3-plans'] });
      queryClient.invalidateQueries({ queryKey: ['plans'] });
    },
  });
}

export function useV3UserWallet(userId: string) {
  return useQuery({
    queryKey: ['v3-user-wallet', userId],
    queryFn: () => httpClient.get<V3WalletView>(`/api/v3/users/${userId}/credits`),
    enabled: !!userId,
  });
}
