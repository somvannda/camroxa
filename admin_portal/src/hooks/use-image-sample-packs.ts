import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient, { apiClient } from '@/lib/http-client';
import type {
  ImageSamplePackCreateRequest,
  ImageSamplePackListResponse,
  ImageSamplePackRecord,
  ImageSamplePackUpdateRequest,
} from '@/types/image-sample-packs';

const imageSamplePackKeys = {
  all: ['image-sample-packs'] as const,
  list: () => ['image-sample-packs', 'list'] as const,
};

export function useImageSamplePacks() {
  return useQuery({
    queryKey: imageSamplePackKeys.list(),
    queryFn: () =>
      httpClient.get<ImageSamplePackListResponse>('/api/v1/admin/image-sample-packs'),
  });
}

export function useCreateImageSamplePack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ImageSamplePackCreateRequest) =>
      httpClient.post<ImageSamplePackRecord>('/api/v1/admin/image-sample-packs', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imageSamplePackKeys.all });
    },
  });
}

export function useUpdateImageSamplePack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { packId: string; patch: ImageSamplePackUpdateRequest }) =>
      httpClient.patch<ImageSamplePackRecord>(
        `/api/v1/admin/image-sample-packs/${payload.packId}`,
        payload.patch,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imageSamplePackKeys.all });
    },
  });
}

export function useDeleteImageSamplePack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (packId: string) =>
      httpClient.delete<{ ok: boolean }>(`/api/v1/admin/image-sample-packs/${packId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imageSamplePackKeys.all });
    },
  });
}

export function useUploadImageSamplePack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      file: File;
      category: 'background' | 'thumbnail';
      name: string;
      is_active?: boolean;
      sort_order?: number;
      version_label?: string | null;
      notes?: string | null;
      packId?: string;
    }) => {
      const form = new FormData();
      form.append('file', payload.file);
      form.append('category', payload.category);
      form.append('name', payload.name);
      form.append('is_active', String(payload.is_active ?? true));
      form.append('sort_order', String(payload.sort_order ?? 0));
      if (payload.version_label) form.append('version_label', payload.version_label);
      if (payload.notes) form.append('notes', payload.notes);
      const path = payload.packId
        ? `/api/v1/admin/image-sample-packs/${payload.packId}/upload`
        : '/api/v1/admin/image-sample-packs/upload';
      const response = await apiClient.post<ImageSamplePackRecord>(path, form);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: imageSamplePackKeys.all });
    },
  });
}

