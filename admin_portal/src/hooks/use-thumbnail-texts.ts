import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient, { apiClient } from '@/lib/http-client';
import type {
  ThumbnailTextCreateRequest,
  ThumbnailTextDeleteAllResponse,
  ThumbnailTextImportResponse,
  ThumbnailTextListResponse,
  ThumbnailTextRecord,
  ThumbnailTextUpdateRequest,
} from '@/types/thumbnail-texts';

const keys = {
  all: ['thumbnail-texts'] as const,
};

export function useThumbnailTexts() {
  return useQuery({
    queryKey: keys.all,
    queryFn: () =>
      httpClient.get<ThumbnailTextListResponse>('/api/v3/admin/thumbnail-texts'),
  });
}

export function useCreateThumbnailText() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ThumbnailTextCreateRequest) =>
      httpClient.post<ThumbnailTextRecord>('/api/v3/admin/thumbnail-texts', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useUpdateThumbnailText() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { id: string; patch: ThumbnailTextUpdateRequest }) =>
      httpClient.patch<ThumbnailTextRecord>(
        `/api/v3/admin/thumbnail-texts/${payload.id}`,
        payload.patch,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useDeleteThumbnailText() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete<{ ok: boolean }>(`/api/v3/admin/thumbnail-texts/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useDeleteAllThumbnailTexts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.delete<ThumbnailTextDeleteAllResponse>(
        '/api/v3/admin/thumbnail-texts',
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useImportThumbnailTexts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const response = await apiClient.post<ThumbnailTextImportResponse>(
        '/api/v3/admin/thumbnail-texts/import',
        form,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}
