import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type StreamingConfig = {
  bucket: string;
  region: string;
  endpoint: string;
  cdn_base_url: string;
  stream_url_ttl_seconds: number;
  key_id_masked: string;
  application_key_masked: string;
  secret_source: string;
  configured: boolean;
};

export type StreamingCatalogTrack = {
  id: string;
  title: string;
  album_name: string;
  artist_name?: string | null;
  variant: string;
  publish_status: string;
  storage_key: string;
  genre?: string | null;
  duration_seconds?: number | null;
  cover_url?: string | null;
  has_lyrics?: boolean;
  suno_image_url?: string | null;
  created_at?: string | null;
};

export type StreamingCatalogAlbum = {
  id: string;
  album_name: string;
  artist_name?: string | null;
  track_count: number;
  published_track_count: number;
  publish_status: string;
  genre?: string | null;
  cover_url?: string | null;
  cover_storage_key?: string | null;
  created_at?: string | null;
};

export type StreamingUploadJob = {
  id: string;
  kind: string;
  status: string;
  source_url?: string | null;
  storage_key?: string | null;
  error?: string | null;
  created_at?: string | null;
};

function invalidateCatalog(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['streaming-catalog'] });
  queryClient.invalidateQueries({ queryKey: ['streaming-albums'] });
}

export function useStreamingConfig() {
  return useQuery({
    queryKey: ['streaming-config'],
    queryFn: () => httpClient.get<StreamingConfig>('/api/v1/admin/streaming/config'),
  });
}

export function useUpdateStreamingConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      key_id: string;
      application_key?: string;
      bucket: string;
      region: string;
      endpoint: string;
      cdn_base_url: string;
      stream_url_ttl_seconds: number;
    }) => httpClient.put<StreamingConfig>('/api/v1/admin/streaming/config', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['streaming-config'] }),
  });
}

export function useStreamingCatalog() {
  return useQuery({
    queryKey: ['streaming-catalog'],
    queryFn: async () => {
      const data = await httpClient.get<{ items: StreamingCatalogTrack[] }>(
        '/api/v1/admin/streaming/catalog',
        { limit: 500 },
      );
      return data.items ?? [];
    },
  });
}

export function useStreamingAlbums() {
  return useQuery({
    queryKey: ['streaming-albums'],
    queryFn: async () => {
      const data = await httpClient.get<{ items: StreamingCatalogAlbum[] }>(
        '/api/v1/admin/streaming/catalog/albums',
        { limit: 500 },
      );
      return data.items ?? [];
    },
  });
}

export function useStreamingUploadJobs(status?: string) {
  return useQuery({
    queryKey: ['streaming-upload-jobs', status ?? 'all'],
    queryFn: async () => {
      const data = await httpClient.get<{ items: StreamingUploadJob[] }>(
        '/api/v1/admin/streaming/upload-jobs',
        { limit: 100, ...(status ? { status } : {}) },
      );
      return data.items ?? [];
    },
  });
}

export function useUnpublishTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.post(`/api/v1/admin/streaming/tracks/${trackId}/unpublish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRepublishTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.post(`/api/v1/admin/streaming/tracks/${trackId}/republish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useDeleteTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.delete(`/api/v1/admin/streaming/tracks/${trackId}`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useUnpublishAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: string) =>
      httpClient.post(`/api/v1/admin/streaming/albums/${albumId}/unpublish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRepublishAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: string) =>
      httpClient.post(`/api/v1/admin/streaming/albums/${albumId}/republish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useDeleteAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: string) =>
      httpClient.delete(`/api/v1/admin/streaming/albums/${albumId}`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRetryUploadJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      httpClient.post(`/api/v1/admin/streaming/upload-jobs/${jobId}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['streaming-upload-jobs'] });
      invalidateCatalog(queryClient);
    },
  });
}

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '—';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

export { formatDuration };

export function useSyncTrackMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.post<{ ok: boolean; track_id?: string; genre?: string | null }>(
        `/api/v1/admin/streaming/tracks/${trackId}/sync-metadata`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useSyncAllMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (limit?: number) =>
      httpClient.post<{ ok: boolean; synced: number; failed: Array<{ track_id: string; error: string }>; total: number }>(
        `/api/v1/admin/streaming/catalog/sync-metadata?limit=${limit ?? 100}`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useUpdateTrackGenre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { trackId: string; genre: string }) =>
      httpClient.patch<StreamingCatalogTrack>(
        `/api/v1/admin/streaming/tracks/${payload.trackId}`,
        { genre: payload.genre },
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}
