import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  InviteProgramResponse,
  InviteProgramSettings,
  InviteProgramStatus,
} from '@/types/models';

export type InviteProgramParams = {
  page: number;
  pageSize: number;
  status?: InviteProgramStatus | '';
  q?: string;
};

export function useInviteProgram(params: InviteProgramParams) {
  return useQuery({
    queryKey: ['invite-program', params],
    queryFn: () =>
      httpClient.get<InviteProgramResponse>('/api/v3/admin/invite-program', {
        page: params.page,
        page_size: params.pageSize,
        status: params.status || undefined,
        q: params.q || undefined,
      }),
  });
}

export function useUpdateInviteSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: InviteProgramSettings) =>
      httpClient.put<InviteProgramSettings>('/api/v3/admin/invite-program/settings', settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-program'] });
    },
  });
}

export function useRejectInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post<{ ok: boolean }>(`/api/v3/admin/invite-program/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-program'] });
    },
  });
}

export function useRestoreInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post<{ ok: boolean }>(`/api/v3/admin/invite-program/${id}/restore`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-program'] });
    },
  });
}
