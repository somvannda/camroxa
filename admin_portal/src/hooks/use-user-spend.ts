import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { UserSpendListParams } from '@/types/api';
import type { UserSpendListResponse } from '@/types/models';

export function useUserSpend(params: UserSpendListParams) {
  return useQuery({
    queryKey: ['user-spend', params],
    queryFn: () =>
      httpClient.get<UserSpendListResponse>(
        '/api/v3/admin/user-spend',
        params as Record<string, unknown>,
      ),
  });
}
