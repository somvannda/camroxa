import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  CreateRedeemCodeRequest,
  RedeemRedemptionListParams,
  UpdateRedeemCodeRequest,
} from '@/types/api';
import type { RedeemCode, RedeemCodeRedemptionListResponse } from '@/types/models';

export function useRedeemCodes() {
  return useQuery({
    queryKey: ['redeem-codes'],
    queryFn: () => httpClient.get<RedeemCode[]>('/api/v1/redeem-codes'),
  });
}

export function useRedeemCodeRedemptions(params: RedeemRedemptionListParams) {
  return useQuery({
    queryKey: ['redeem-code-redemptions', params],
    queryFn: () =>
      httpClient.get<RedeemCodeRedemptionListResponse>(
        '/api/v1/redeem-codes/redemptions',
        params as Record<string, unknown>,
      ),
  });
}

export function useCreateRedeemCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateRedeemCodeRequest) =>
      httpClient.post<RedeemCode>('/api/v1/redeem-codes', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['redeem-codes'] });
      queryClient.invalidateQueries({ queryKey: ['redeem-code-redemptions'] });
    },
  });
}

export function useUpdateRedeemCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; payload: UpdateRedeemCodeRequest }) =>
      httpClient.put<RedeemCode>(`/api/v1/redeem-codes/${data.id}`, data.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['redeem-codes'] });
      queryClient.invalidateQueries({ queryKey: ['redeem-code-redemptions'] });
    },
  });
}

export function useDeleteRedeemCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<void>(`/api/v1/redeem-codes/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['redeem-codes'] });
      queryClient.invalidateQueries({ queryKey: ['redeem-code-redemptions'] });
    },
  });
}
