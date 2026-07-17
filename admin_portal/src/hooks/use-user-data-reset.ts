import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type {
  BackupListResponse,
  ResetResult,
  RestoreResult,
} from '@/types/user-data-reset';

const BACKUP_LIST_KEY = ['user-data', 'backups'];

export function useBackupList() {
  return useQuery({
    queryKey: BACKUP_LIST_KEY,
    queryFn: async () => {
      const response = await httpClient.get<BackupListResponse>(
        '/api/v1/admin/user-data/backups',
      );
      return response.backups;
    },
  });
}

export function useResetUserData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { password: string }) =>
      httpClient.post<ResetResult>('/api/v1/admin/user-data/reset', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BACKUP_LIST_KEY });
    },
  });
}

export function useRestoreUserData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { backup_filename: string; password: string }) =>
      httpClient.post<RestoreResult>('/api/v1/admin/user-data/restore', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BACKUP_LIST_KEY });
    },
  });
}
