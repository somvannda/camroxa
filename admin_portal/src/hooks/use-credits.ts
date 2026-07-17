import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type {
  CreditAdjustmentRequest,
  CreateCreditPackRequest,
  CreateModelCostRequest,
  CreatePricingRequest,
  GeneratePricingRequest,
  UpdateCreditPackRequest,
  UpdateGlobalCreditValueRequest,
} from '@/types/api';
import type { CreditPricing, CreditPack, ModelCost, ServiceAvailabilityEntry, GlobalCreditValueResponse } from '@/types/models';

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
    mutationFn: (data: { ai_service: string; operation_type: string; sub_model?: string }) =>
      httpClient.delete(
        `/api/v1/credits/pricing?ai_service=${encodeURIComponent(data.ai_service)}&operation_type=${encodeURIComponent(data.operation_type)}&sub_model=${encodeURIComponent(data.sub_model ?? '')}`,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pricing'] }),
  });
}

export function useDeleteAllPricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ai_service?: string) => {
      const params = ai_service
        ? `?ai_service=${encodeURIComponent(ai_service)}`
        : '';
      return httpClient.delete<{ deleted_count: number }>(
        `/api/v1/credits/pricing/all${params}`,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['ai-routing', 'audit'] });
    },
  });
}

export function useApprovePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      ai_service?: string;
      operation_type?: string;
      entries?: Array<{ ai_service: string; operation_type: string; sub_model?: string }>;
    }) => httpClient.post('/api/v1/credits/pricing/approve', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['ai-routing', 'audit'] });
    },
  });
}

export function useSyncRoutingPricing() {
  const queryClient = useQueryClient();
  return useMutation<{ created_count?: number }, Error, void>({
    mutationFn: () => httpClient.post<{ created_count?: number }>('/api/v1/admin/ai-routing/sync-pricing', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['ai-routing', 'audit'] });
    },
  });
}

export function useAdminCreditPacks() {
  return useQuery({
    queryKey: ['credit-packs', 'admin'],
    queryFn: () => httpClient.get<CreditPack[]>('/api/v1/credits/admin/packs'),
  });
}

export function usePacks() {
  return useQuery({
    queryKey: ['credit-packs', 'storefront'],
    queryFn: () => httpClient.get<CreditPack[]>('/api/v1/credits/packs'),
  });
}

export function useCreateCreditPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCreditPackRequest) =>
      httpClient.post<CreditPack>('/api/v1/credits/admin/packs', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-packs'] });
    },
  });
}

export function useUpdateCreditPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateCreditPackRequest) =>
      httpClient.put<CreditPack>('/api/v1/credits/admin/packs', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-packs'] });
    },
  });
}

export function useDeleteCreditPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (packId: string) =>
      httpClient.delete(`/api/v1/credits/admin/packs?pack_id=${encodeURIComponent(packId)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-packs'] });
    },
  });
}

export function useAdjustBalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreditAdjustmentRequest) =>
      httpClient.post('/api/v1/credits/adjust', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['credit-packs'] });
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

export function useModelCosts() {
  return useQuery({
    queryKey: ['model-costs'],
    queryFn: () => httpClient.get<ModelCost[]>('/api/v1/credits/model-costs'),
  });
}

export function useCreateModelCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateModelCostRequest) =>
      httpClient.post<ModelCost>('/api/v1/credits/model-costs', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model-costs'] }),
  });
}

export function useUpdateModelCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateModelCostRequest) =>
      httpClient.put<ModelCost>('/api/v1/credits/model-costs', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model-costs'] }),
  });
}

export function useDeleteModelCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { ai_service: string; operation_type: string; sub_model?: string }) =>
      httpClient.delete(
        `/api/v1/credits/model-costs?ai_service=${encodeURIComponent(data.ai_service)}&operation_type=${encodeURIComponent(data.operation_type)}&sub_model=${encodeURIComponent(data.sub_model ?? '')}`,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model-costs'] }),
  });
}

export function useSeedModelCosts() {
  const queryClient = useQueryClient();
  return useMutation<
    { seeded_count: number; skipped_existing_count: number },
    Error,
    boolean
  >({
    mutationFn: (overwrite = false) =>
      httpClient.post<{ seeded_count: number; skipped_existing_count: number }>(
        `/api/v1/credits/model-costs/seed?overwrite=${overwrite}`,
        {},
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model-costs'] }),
  });
}

export function useGeneratePricing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GeneratePricingRequest) =>
      httpClient.post('/api/v1/credits/pricing/generate', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pricing'] });
      queryClient.invalidateQueries({ queryKey: ['ai-routing', 'audit'] });
    },
  });
}
