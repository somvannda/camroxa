import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreditAdjustmentRequest, CreatePricingRequest, UpdateGlobalCreditValueRequest } from '@/types/api';
import type { CreditPricing, CreditPack, ServiceAvailabilityEntry, GlobalCreditValueResponse } from '@/types/models';

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
    mutationFn: (data: CreatePricingRequest) =>
      httpClient.put<CreditPricing>('/api/v1/credits/pricing', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pricing'] }),
  });
}

export function useDeletePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { ai_service: string; operation_type: string }) =>
      httpClient.delete(`/api/v1/credits/pricing?ai_service=${encodeURIComponent(data.ai_service)}&operation_type=${encodeURIComponent(data.operation_type)}`),
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

export function useServiceAvailability() {
  return useQuery({
    queryKey: ['service-availability'],
    queryFn: () =>
      httpClient.get<ServiceAvailabilityEntry[]>('/api/v1/credits/service-availability'),
  });
}

export function useGlobalCreditValue() {
  return useQuery({
    queryKey: ['global-credit-value'],
    queryFn: () =>
      httpClient.get<GlobalCreditValueResponse>('/api/v1/credits/global-credit-value'),
  });
}

export function useUpdateGlobalCreditValue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateGlobalCreditValueRequest) =>
      httpClient.put<GlobalCreditValueResponse>('/api/v1/credits/global-credit-value', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['global-credit-value'] });
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
    },
  });
}
