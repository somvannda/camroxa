import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreateOfferRequest } from '@/types/api';
import type { Plan, PlanOffer } from '@/types/models';

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: () => httpClient.get<Plan[]>('/api/v3/plans'),
  });
}

export function useCreatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      price_cents: number;
      profile_allowance: number;
      monthly_song_limit: number | null;
      monthly_image_limit: number | null;
      monthly_draft_limit: number | null;
      monthly_video_limit?: number | null;
      monthly_merge_limit?: number | null;
      billing_cycle_days: number | null;
      daily_song_limit_per_channel: number;
      daily_image_limit_per_channel: number;
      daily_draft_limit_per_channel: number;
      daily_video_limit?: number;
      daily_merge_limit?: number;
      plan_kind?: 'subscription' | 'profile_addon';
    }) => httpClient.post<Plan>('/api/v3/plans', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['v3-plans'] });
    },
  });
}

export function useUpdatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<Plan> }) =>
      httpClient.patch<Plan>(`/api/v3/plans/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plans'] }),
  });
}

export function useDeletePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<void>(`/api/v3/plans/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['offers'] });
    },
  });
}

export function useOffers() {
  return useQuery({
    queryKey: ['offers'],
    queryFn: () => httpClient.get<PlanOffer[]>('/api/v3/plans/offers'),
  });
}

export function useCreateOffer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateOfferRequest) =>
      httpClient.post<PlanOffer>('/api/v3/plans/offers', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offers'] }),
  });
}

export type PlanTermDiscounts = {
  semi_annual_discount_percent: number;
  annual_discount_percent: number;
};

export function usePlanTermDiscounts() {
  return useQuery({
    queryKey: ['plan-term-discounts'],
    queryFn: () => httpClient.get<PlanTermDiscounts>('/api/v3/plans/term-discounts'),
  });
}

export function useUpdatePlanTermDiscounts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PlanTermDiscounts) =>
      httpClient.put<PlanTermDiscounts>('/api/v3/plans/term-discounts', data),
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['plan-term-discounts'] });
          queryClient.invalidateQueries({ queryKey: ['plans'] });
        },
  });
}

export function useSyncTermPlanPrices() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.post<{ updated_plan_ids: string[]; skipped: string[] }>(
        '/api/v3/plans/sync-term-prices',
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['plan-price-drift'] });
    },
  });
}

export type PlanPriceDriftItem = {
  plan_id: string;
  plan_name: string;
  billing_cycle_days: number;
  profile_allowance: number;
  stored_cents: number;
  expected_cents: number;
  plan_kind: string;
};

export function usePlanPriceDrift() {
  return useQuery({
    queryKey: ['plan-price-drift'],
    queryFn: () =>
      httpClient.get<{ drift_count: number; items: PlanPriceDriftItem[] }>(
        '/api/v3/plans/term-price-drift',
      ),
  });
}
