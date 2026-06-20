import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';

export interface SystemSetting {
  key: string;
  value: string;
  value_type: string;
  updated_at: string | null;
}

interface SystemSettingsResponse {
  settings: SystemSetting[];
}

export function useSystemSettings() {
  return useQuery({
    queryKey: ['system-settings'],
    queryFn: () => httpClient.get<SystemSettingsResponse>('/api/v1/admin/system-settings'),
  });
}

export function useUpsertSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { key: string; value: string; value_type?: string }) =>
      httpClient.put<SystemSetting>('/api/v1/admin/system-settings', {
        key: data.key,
        value: data.value,
        value_type: data.value_type ?? 'string',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['system-settings'] }),
  });
}

export function useDeleteSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: string) =>
      httpClient.delete(`/api/v1/admin/system-settings/${key}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['system-settings'] }),
  });
}
