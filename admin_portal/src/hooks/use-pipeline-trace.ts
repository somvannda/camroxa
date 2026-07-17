import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { AdminBatchSummary, AdminSongSummary } from '@/types/models';

export function useAdminBatch(batchId: string | null) {
  return useQuery({
    queryKey: ['admin-batch', batchId],
    enabled: Boolean(batchId),
    queryFn: () => httpClient.get<AdminBatchSummary>(`/api/v1/admin/batches/${batchId}`),
  });
}

export function useAdminSong(songId: string | null) {
  return useQuery({
    queryKey: ['admin-song', songId],
    enabled: Boolean(songId),
    queryFn: () => httpClient.get<AdminSongSummary>(`/api/v1/admin/songs/${songId}`),
  });
}
