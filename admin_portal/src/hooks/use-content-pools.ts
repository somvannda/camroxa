import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  ContentPoolKind,
  ContentPoolListResponse,
  ContentPoolPresetConfig,
  ContentPoolPresetPack,
  ContentPoolPresetPackListResponse,
  ContentPoolRow,
  ContentPoolStatsResponse,
  GenerateContentPoolResponse,
  GeneratePresetPackBanksResponse,
} from '@/types/content-pools';

const contentPoolKeys = {
  all: ['content-pools'] as const,
  stats: () => ['content-pools', 'stats'] as const,
  list: (kind: ContentPoolKind, limit: number, offset: number) => ['content-pools', 'list', kind, limit, offset] as const,
  presetPacks: (kind: ContentPoolKind) => ['content-pools', 'preset-packs', kind] as const,
};

export function useContentPoolStats() {
  return useQuery({
    queryKey: contentPoolKeys.stats(),
    queryFn: () => httpClient.get<ContentPoolStatsResponse>('/api/v1/admin/content-pools/stats'),
  });
}

export function useContentPoolItems(kind: ContentPoolKind, limit: number, offset: number) {
  return useQuery({
    queryKey: contentPoolKeys.list(kind, limit, offset),
    queryFn: () => httpClient.get<ContentPoolListResponse>(`/api/v1/admin/content-pools/${kind}`, { limit, offset }),
    enabled: !!kind,
  });
}

export function useGenerateContentPool(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { count: number; presetPackId?: string | null }) =>
      httpClient.post<GenerateContentPoolResponse>(`/api/v1/admin/content-pools/${kind}/generate`, {
        count: payload.count,
        preset_pack_id: payload.presetPackId ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.all });
    },
  });
}

export function useImportContentPool(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) =>
      httpClient.post<{ inserted: number }>(`/api/v1/admin/content-pools/${kind}/import`, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.all });
    },
  });
}

export function useUpdateContentPoolItem(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { itemId: number; text: string; secondaryText?: string | null }) =>
      httpClient.patch<ContentPoolRow>(`/api/v1/admin/content-pools/${kind}/${payload.itemId}`, {
        text: payload.text,
        secondary_text: payload.secondaryText ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.all });
    },
  });
}

export function useDeleteContentPoolItem(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: number) =>
      httpClient.delete<void>(`/api/v1/admin/content-pools/${kind}/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.all });
    },
  });
}

export function useClearContentPool(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.post<{ ok: boolean }>(`/api/v1/admin/content-pools/${kind}/clear`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.all });
    },
  });
}

export function useContentPoolPresetPacks(kind: ContentPoolKind) {
  return useQuery({
    queryKey: contentPoolKeys.presetPacks(kind),
    queryFn: () =>
      httpClient.get<ContentPoolPresetPackListResponse>(`/api/v1/admin/content-pools/preset-packs/${kind}`),
    enabled: !!kind,
  });
}

export function useCreateContentPoolPresetPack(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      description: string;
      isActive: boolean;
      config: ContentPoolPresetConfig;
    }) =>
      httpClient.post<ContentPoolPresetPack>(`/api/v1/admin/content-pools/preset-packs/${kind}`, {
        name: payload.name,
        description: payload.description,
        is_active: payload.isActive,
        config: payload.config,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.presetPacks(kind) });
    },
  });
}

export function useUpdateContentPoolPresetPack(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      presetPackId: string;
      name: string;
      description: string;
      isActive: boolean;
      config: ContentPoolPresetConfig;
    }) =>
      httpClient.patch<ContentPoolPresetPack>(
        `/api/v1/admin/content-pools/preset-packs/${kind}/${payload.presetPackId}`,
        {
          name: payload.name,
          description: payload.description,
          is_active: payload.isActive,
          config: payload.config,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.presetPacks(kind) });
    },
  });
}

export function useDeleteContentPoolPresetPack(kind: ContentPoolKind) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (presetPackId: string) =>
      httpClient.delete<void>(`/api/v1/admin/content-pools/preset-packs/${kind}/${presetPackId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: contentPoolKeys.presetPacks(kind) });
    },
  });
}

export function useGenerateContentPoolPresetBanks(kind: ContentPoolKind) {
  return useMutation({
    mutationFn: (payload: { targetCount: number }) =>
      httpClient.post<GeneratePresetPackBanksResponse>(
        `/api/v1/admin/content-pools/preset-packs/${kind}/generate-banks`,
        {
          target_count: payload.targetCount,
        },
      ),
  });
}
