import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type PlaybackEvent = {
  id: number | string;
  user_id?: string | null;
  device_id?: string | null;
  session_id?: string | null;
  subject_type?: string | null;
  subject_id?: string | null;
  variant?: string | null;
  event: string;
  bytes_served?: number;
  package_status?: string | null;
  created_at?: string | null;
};

export type ExportEvent = {
  id: string;
  user_id: string;
  device_id?: string | null;
  suno_task_id?: string | null;
  variant?: string | null;
  format: string;
  watermark_id?: string | null;
  actor: string;
  created_at?: string | null;
};

type EventPage<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export function usePlaybackEvents(params: { userId?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ['playback-events', params.userId ?? '', params.limit, params.offset],
    queryFn: () =>
      httpClient.get<EventPage<PlaybackEvent>>('/api/v3/web-music/licenses/admin/playback-events', {
        user_id: params.userId || undefined,
        limit: params.limit,
        offset: params.offset,
      }),
  });
}

export function useExportEvents(params: { userId?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ['export-events', params.userId ?? '', params.limit, params.offset],
    queryFn: () =>
      httpClient.get<EventPage<ExportEvent>>('/api/v3/web-music/licenses/admin/export-events', {
        user_id: params.userId || undefined,
        limit: params.limit,
        offset: params.offset,
      }),
  });
}

export function useBackfillAudioPackages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (limit: number) =>
      httpClient.post<{ packaged: number }>(
        `/api/v3/web-music/licenses/admin/backfill?limit=${limit}`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['streaming-catalog'] });
    },
  });
}
