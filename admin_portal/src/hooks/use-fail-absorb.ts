import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';

export interface FailAbsorbStatus {
  user_id: string;
  usage_date: string;
  fail_absorb_used: number;
  fail_absorb_budget: number;
  remaining: number | null;
  blocked: boolean;
  redis_key: string;
  fail_absorb_used_before?: number | null;
}

export function useFailAbsorb(userId: string) {
  return useQuery({
    queryKey: ['users', userId, 'fail-absorb'],
    queryFn: () =>
      httpClient.get<FailAbsorbStatus>(`/api/v1/users/${userId}/fail-absorb`),
    enabled: !!userId,
    refetchInterval: 30_000,
  });
}

export function useResetFailAbsorb(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.post<FailAbsorbStatus>(`/api/v1/users/${userId}/fail-absorb/reset`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users', userId, 'fail-absorb'] });
    },
  });
}
