import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  CreateMusicLanguageRequest,
  MusicLanguage,
  MusicLanguageListResponse,
  UpdateMusicLanguageRequest,
} from '@/types/music-languages';

const musicLanguageKeys = {
  all: ['music-languages'] as const,
  list: () => ['music-languages', 'list'] as const,
};

export function useMusicLanguages() {
  return useQuery({
    queryKey: musicLanguageKeys.list(),
    queryFn: () => httpClient.get<MusicLanguageListResponse>('/api/v3/admin/music-languages'),
  });
}

export function useCreateMusicLanguage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateMusicLanguageRequest) =>
      httpClient.post<MusicLanguage>('/api/v3/admin/music-languages', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: musicLanguageKeys.all });
    },
  });
}

export function useUpdateMusicLanguage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, patch }: { code: string; patch: UpdateMusicLanguageRequest }) =>
      httpClient.patch<MusicLanguage>(`/api/v3/admin/music-languages/${encodeURIComponent(code)}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: musicLanguageKeys.all });
    },
  });
}

export function useDeleteMusicLanguage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      httpClient.delete<void>(`/api/v3/admin/music-languages/${encodeURIComponent(code)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: musicLanguageKeys.all });
    },
  });
}
