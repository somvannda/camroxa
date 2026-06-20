import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreateOfferRequest } from '@/types/api';
import type { Plan, PlanOffer } from '@/types/models';

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: () => httpClient.get<Plan[]>('/api/v1/plans'),
  });
}

export function useCreatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      price_cents: number;
      profile_allowance: number;
      monthly_song_quota: number | null;
      billing_cycle_days: number | null;
      daily_song_limit_per_channel?: number;
    }) => httpClient.post<Plan>('/api/v1/plans', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plans'] }),
  });
}

export function useUpdatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<Plan> }) =>
      httpClient.patch<Plan>(`/api/v1/plans/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plans'] }),
  });
}

export function useOffers() {
  return useQuery({
    queryKey: ['offers'],
    queryFn: () => httpClient.get<PlanOffer[]>('/api/v1/plans/offers'),
  });
}

export function useCreateOffer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateOfferRequest) =>
      httpClient.post<PlanOffer>('/api/v1/plans/offers', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offers'] }),
  });
}
