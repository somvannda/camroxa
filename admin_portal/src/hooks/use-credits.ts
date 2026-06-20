import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreditAdjustmentRequest, CreatePricingRequest } from '@/types/api';
import type { CreditPricing, CreditPack } from '@/types/models';

export function usePricing() {
  return useQuery({
    queryKey: ['pricing'],
    queryFn: () => httpClient.get<CreditPricing[]>('/api/v1/credits/pricing'),
  });
}

export function useCreatePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePricingRequest) =>
      httpClient.post<CreditPricing>('/api/v1/credits/pricing', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pricing'] }),
  });
}

export function useUpdatePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<CreatePricingRequest> }) =>
      httpClient.put<CreditPricing>(`/api/v1/credits/pricing/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pricing'] }),
  });
}

export function usePacks() {
  return useQuery({
    queryKey: ['packs'],
    queryFn: () => httpClient.get<CreditPack[]>('/api/v1/credits/packs'),
  });
}

export function useAdjustBalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreditAdjustmentRequest) =>
      httpClient.post('/api/v1/credits/adjust', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['packs'] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
