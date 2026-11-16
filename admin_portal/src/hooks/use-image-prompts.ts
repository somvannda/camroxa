import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
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
