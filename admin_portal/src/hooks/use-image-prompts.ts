import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient, { apiClient } from '@/lib/http-client';
import type {
  ImagePromptImportResponse,
  ImagePromptStyleCreateRequest,
  ImagePromptStyleListResponse,
  ImagePromptStyleRecord,
  ImagePromptStyleUpdateRequest,
} from '@/types/image-prompts';

const imagePromptKeys = {
  all: ['image-prompts'] as const,
  list: (kind?: string) => ['image-prompts', 'list', kind ?? 'all'] as const,
};

export function useImagePrompts(kind?: string) {
  return useQuery({
    queryKey: imagePromptKeys.list(kind),
    queryFn: () =>
      httpClient.get<ImagePromptStyleListResponse>(
        '/api/v3/admin/image-prompts',
        kind ? { kind } : undefined,
      ),
  });
}

export function useCreateImagePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ImagePromptStyleCreateRequest) =>
      httpClient.post<ImagePromptStyleRecord>('/api/v3/admin/image-prompts', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imagePromptKeys.all });
    },
  });
}

export function useUpdateImagePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { styleId: string; patch: ImagePromptStyleUpdateRequest }) =>
      httpClient.patch<ImagePromptStyleRecord>(
        `/api/v3/admin/image-prompts/${payload.styleId}`,
        payload.patch,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imagePromptKeys.all });
    },
  });
}

export function useDeleteImagePrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (styleId: string) =>
      httpClient.delete<{ ok: boolean }>(`/api/v3/admin/image-prompts/${styleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imagePromptKeys.all });
    },
  });
}

export function useImportImagePrompts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const response = await apiClient.post<ImagePromptImportResponse>(
        '/api/v3/admin/image-prompts/import',
        form,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imagePromptKeys.all });
    },
  });
}
