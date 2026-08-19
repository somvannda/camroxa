import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type { WebMusicPlan, WebMusicTopupPack } from '@/types/models';

export function useWebMusicPlans() {
  return useQuery({
    queryKey: ['web-music-plans'],
    queryFn: () => httpClient.get<WebMusicPlan[]>('/api/v1/plans/web-music/plans'),
  });
}

export function useCreateWebMusicPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      price_cents: number;
      billing_cycle_days: number;
      monthly_credits: number;
      features: WebMusicPlan['features'];
      is_public: boolean;
      display_order: number;
    }) => httpClient.post<WebMusicPlan>('/api/v1/plans/web-music/plans', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-plans'] }),
  });
}

export function useUpdateWebMusicPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<Omit<WebMusicPlan, 'id' | 'subscriber_count' | 'can_delete' | 'created_at' | 'updated_at'>> }) =>
      httpClient.patch<WebMusicPlan>(`/api/v1/plans/web-music/plans/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-plans'] }),
  });
}

export function useDeleteWebMusicPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<void>(`/api/v1/plans/web-music/plans/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-plans'] }),
  });
}

export function useWebMusicTopups() {
  return useQuery({
    queryKey: ['web-music-topups'],
    queryFn: () => httpClient.get<WebMusicTopupPack[]>('/api/v1/plans/web-music/topups'),
  });
}

export function useCreateWebMusicTopup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      slug: string;
      name: string;
      total_credits: number;
      price_cents: number;
      display_order: number;
      is_active: boolean;
    }) => httpClient.post<WebMusicTopupPack>('/api/v1/plans/web-music/topups', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-topups'] }),
  });
}

export function useUpdateWebMusicTopup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<Omit<WebMusicTopupPack, 'id' | 'songs_equivalent' | 'created_at' | 'updated_at'>> }) =>
      httpClient.patch<WebMusicTopupPack>(`/api/v1/plans/web-music/topups/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-topups'] }),
  });
}

export function useDeleteWebMusicTopup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<void>(`/api/v1/plans/web-music/topups/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['web-music-topups'] }),
  });
}
