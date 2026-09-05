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
  genres?: string[];
  duration_seconds?: number | null;
  play_count?: number;
  cover_url?: string | null;
  has_lyrics?: boolean;
  suno_image_url?: string | null;
  package_status?: string | null;
  created_at?: string | null;
};

export type StreamingCatalogAlbum = {
  id: string;
  album_name: string;
  artist_name?: string | null;
  track_count: number;
  published_track_count: number;
  play_count?: number;
  publish_status: string;
  genre?: string | null;
  genres?: string[];
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
  attempt_count?: number;
  user_id?: string | null;
  user_email?: string | null;
  user_display_name?: string | null;
  song_id?: string | null;
  song_title?: string | null;
  song_album?: string | null;
  song_batch_index?: number | null;
  batch_id?: string | null;
  album_id?: string | null;
  stream_album_name?: string | null;
  stream_channel_role?: string | null;
  stream_album_publish_status?: string | null;
  stream_track_publish_status?: string | null;
  stream_track_variant?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

function invalidateCatalog(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['streaming-catalog'] });
  queryClient.invalidateQueries({ queryKey: ['streaming-albums'] });
}

export function useStreamingConfig() {
  return useQuery({
    queryKey: ['streaming-config'],
    queryFn: () => httpClient.get<StreamingConfig>('/api/v3/admin/streaming/config'),
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
    }) => httpClient.put<StreamingConfig>('/api/v3/admin/streaming/config', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['streaming-config'] }),
  });
}

export type StreamingCatalogListParams = {
  page: number;
  pageSize?: number;
  q?: string;
  publishStatus?: 'all' | 'published' | 'unpublished';
};

export type StreamingCatalogPage = {
  items: StreamingCatalogTrack[];
  total: number;
  limit: number;
  offset: number;
};

export type StreamingAlbumsPage = {
  items: StreamingCatalogAlbum[];
  total: number;
  limit: number;
  offset: number;
};

function catalogQueryParams(params: StreamingCatalogListParams) {
  const limit = params.pageSize ?? 50;
  const offset = Math.max(0, (params.page - 1) * limit);
  const q = params.q?.trim() || undefined;
  const publish_status =
    params.publishStatus && params.publishStatus !== 'all'
      ? params.publishStatus
      : undefined;
  return {
    limit,
    offset,
    ...(q ? { q } : {}),
    ...(publish_status ? { publish_status } : {}),
  };
}

export function useStreamingCatalog(params: StreamingCatalogListParams) {
  const queryParams = catalogQueryParams(params);
  return useQuery({
    queryKey: [
      'streaming-catalog',
      queryParams.limit,
      queryParams.offset,
      queryParams.q ?? '',
      queryParams.publish_status ?? '',
    ],
    queryFn: () =>
      httpClient.get<StreamingCatalogPage>('/api/v3/admin/streaming/catalog', queryParams),
  });
}

export function useStreamingAlbums(params: StreamingCatalogListParams) {
  const queryParams = catalogQueryParams(params);
  return useQuery({
    queryKey: [
      'streaming-albums',
      queryParams.limit,
      queryParams.offset,
      queryParams.q ?? '',
      queryParams.publish_status ?? '',
    ],
    queryFn: () =>
      httpClient.get<StreamingAlbumsPage>(
        '/api/v3/admin/streaming/catalog/albums',
        queryParams,
      ),
  });
}

export type UploadJobsListParams = {
  page: number;
  pageSize?: number;
  status?: string;
  kind?: string;
  q?: string;
};

export type UploadJobsPage = {
  items: StreamingUploadJob[];
  total: number;
  limit: number;
  offset: number;
};

export function useStreamingUploadJobs(params: UploadJobsListParams) {
  const pageSize = params.pageSize ?? 50;
  const offset = Math.max(0, (params.page - 1) * pageSize);
  const status = params.status && params.status !== 'all' ? params.status : undefined;
  const kind = params.kind && params.kind !== 'all' ? params.kind : undefined;
  const q = params.q?.trim() || undefined;
  return useQuery({
    queryKey: [
      'streaming-upload-jobs',
      pageSize,
      offset,
      status ?? 'all',
      kind ?? 'all',
      q ?? '',
    ],
    queryFn: async () => {
      const data = await httpClient.get<UploadJobsPage>(
        '/api/v3/admin/streaming/upload-jobs',
        {
          limit: pageSize,
          offset,
          ...(status ? { status } : {}),
          ...(kind ? { kind } : {}),
          ...(q ? { q } : {}),
        },
      );
      return data;
    },
  });
}

export function useUnpublishTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.post(`/api/v3/admin/streaming/tracks/${trackId}/unpublish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRepublishTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ trackId, force = false }: { trackId: string; force?: boolean }) =>
      httpClient.post(
        `/api/v3/admin/streaming/tracks/${trackId}/republish${force ? '?force=true' : ''}`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useDeleteTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (trackId: string) =>
      httpClient.delete(`/api/v3/admin/streaming/tracks/${trackId}`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useUnpublishAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: string) =>
      httpClient.post(`/api/v3/admin/streaming/albums/${albumId}/unpublish`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRepublishAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ albumId, force = false }: { albumId: string; force?: boolean }) =>
      httpClient.post(
        `/api/v3/admin/streaming/albums/${albumId}/republish${force ? '?force=true' : ''}`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useDeleteAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (albumId: string) =>
      httpClient.delete(`/api/v3/admin/streaming/albums/${albumId}`),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useRetryUploadJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      httpClient.post(`/api/v3/admin/streaming/upload-jobs/${jobId}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['streaming-upload-jobs'] });
      invalidateCatalog(queryClient);
    },
  });
}

export type RetryAllSweepStatus = {
  running: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  total: number;
  scanned: number;
  succeeded: number;
  still_failed: number;
  remaining: number;
  /** Live count of failed mp3_ok/mp3_alt upload jobs in the DB right now. */
  failed_mp3_now?: number;
  /** All-time successes that required at least one retry (attempt_count > 1). */
  retried_success_total?: number;
  last_errors?: Array<{ job_id: string; error: string }>;
};

export function useStartRetryAllUploads() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.post<{ started: boolean; running: boolean; total: number }>(
        '/api/v3/admin/streaming/upload-jobs/retry-all',
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['streaming-upload-sweep-status'] });
    },
  });
}

export function useRetryAllUploadSweepStatus() {
  return useQuery({
    queryKey: ['streaming-upload-sweep-status'],
    queryFn: () =>
      httpClient.get<RetryAllSweepStatus>(
        '/api/v3/admin/streaming/upload-jobs/retry-all/status',
      ),
    refetchInterval: (query) => (query.state.data?.running === true ? 3000 : false),
    refetchOnWindowFocus: false,
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
        `/api/v3/admin/streaming/tracks/${trackId}/sync-metadata`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useSyncAllMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (limit?: number) =>
      httpClient.post<{ ok: boolean; synced: number; failed: Array<{ track_id: string; error: string }>; total: number }>(
        `/api/v3/admin/streaming/catalog/sync-metadata?limit=${limit ?? 100}`,
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}

export function useUpdateTrackGenre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { trackId: string; genre: string }) =>
      httpClient.patch<StreamingCatalogTrack>(
        `/api/v3/admin/streaming/tracks/${payload.trackId}`,
        { genre: payload.genre },
      ),
    onSuccess: () => invalidateCatalog(queryClient),
  });
}
