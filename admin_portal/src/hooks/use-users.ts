import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import { apiClient } from '@/lib/http-client';
import type { PaginatedResponse, UserListParams } from '@/types/api';
import type { User, UserFullDetail } from '@/types/models';

interface UsersApiResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

export function useUsers(params: UserListParams) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: async () => {
      const resp = await httpClient.get<UsersApiResponse>('/api/v3/users', params as Record<string, unknown>);
      // Map API response (uses 'users' key) to PaginatedResponse format (uses 'items' key)
      return {
        items: resp.users,
        total: resp.total,
        page: resp.page,
        page_size: resp.page_size,
        total_pages: Math.ceil(resp.total / resp.page_size),
      } as PaginatedResponse<User>;
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<User> }) =>
      httpClient.patch<User>(`/api/v3/users/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useSetUserPassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; password: string }) =>
      httpClient.post(`/api/v3/users/${data.id}/set-password`, { password: data.password }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      queryClient.invalidateQueries({ queryKey: ['users', variables.id, 'details'] });
    },
  });
}

export function useSuspendUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; reason: string }) =>
      httpClient.post(`/api/v3/users/${data.id}/suspend`, { reason: data.reason }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useReactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post(`/api/v3/users/${id}/reactivate`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useFreezeGeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; hours: number; reason: string }) =>
      httpClient.post(`/api/v3/users/${data.id}/freeze-generation`, {
        hours: data.hours,
        reason: data.reason,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      queryClient.invalidateQueries({ queryKey: ['users', variables.id, 'details'] });
    },
  });
}

export function useUnfreezeGeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post(`/api/v3/users/${id}/unfreeze-generation`),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      queryClient.invalidateQueries({ queryKey: ['users', variables, 'details'] });
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v3/users/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}


export function useUserDetails(id: string) {
  return useQuery({
    queryKey: ['users', id, 'details'],
    queryFn: () => httpClient.get<UserFullDetail>(`/api/v3/users/${id}/details`),
    enabled: !!id,
  });
}

export function useQuotaTopup(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      quota_kind: 'draft' | 'music' | 'image' | 'video' | 'merge';
      amount: number;
      reason: string;
    }) => httpClient.post(`/api/v3/users/${userId}/quota-topups`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users', userId, 'details'] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useChannelProfileLogoBlob(profileId: string) {
  return useQuery({
    queryKey: ['channel-profiles', profileId, 'logo-blob'],
    queryFn: async () => {
      const resp = await apiClient.get(
        `/api/v3/media/channel-profiles/${profileId}/logo`,
        { responseType: 'blob' },
      );
      return resp.data as Blob;
    },
    enabled: !!profileId,
    retry: false,
  });
}

export function useChannelProfileCoverBlob(profileId: string, index: number) {
  return useQuery({
    queryKey: ['channel-profiles', profileId, 'cover-blob', index],
    queryFn: async () => {
      const resp = await apiClient.get(
        `/api/v3/media/channel-profiles/${profileId}/covers/${index}`,
        { responseType: 'blob' },
      );
      return resp.data as Blob;
    },
    enabled: !!profileId && index >= 0,
    retry: false,
  });
}

export type AdminWebMusicWorkspace = {
  id: string;
  name: string;
  is_default?: boolean;
  created_at?: string | null;
};

export type AdminWebMusicClip = {
  variant: string;
  label: string;
  title?: string | null;
  audio_url: string;
  download_url: string;
  ready: boolean;
  image_url?: string | null;
  duration_seconds?: number | null;
  is_preview?: boolean;
  preview_seconds?: number | null;
};

export type AdminWebMusicGeneration = {
  id: string;
  title: string;
  lyrics: string;
  style: string;
  model: string;
  model_label?: string;
  instrumental: boolean;
  status: string;
  error_message?: string | null;
  created_at?: string | null;
  is_preview?: boolean;
  preview_seconds?: number | null;
  negative_tags?: string | null;
  vocal_gender?: string | null;
  style_weight?: number | null;
  weirdness_constraint?: number | null;
  audio_weight?: number | null;
  clips: AdminWebMusicClip[];
};

export function useUserWebMusicWorkspaces(userId: string) {
  return useQuery({
    queryKey: ['users', userId, 'web-music', 'workspaces'],
    queryFn: () =>
      httpClient.get<{ items: AdminWebMusicWorkspace[] }>(
        `/api/v3/users/${userId}/web-music/workspaces`,
      ),
    enabled: !!userId,
  });
}

export function useUserWebMusicGenerations(userId: string, workspaceId?: string) {
  return useQuery({
    queryKey: ['users', userId, 'web-music', 'generations', workspaceId ?? 'all'],
    queryFn: () =>
      httpClient.get<{ items: AdminWebMusicGeneration[]; total: number }>(
        `/api/v3/users/${userId}/web-music/generations`,
        {
          limit: 40,
          offset: 0,
          ...(workspaceId ? { workspace_id: workspaceId } : {}),
        },
      ),
    enabled: !!userId,
  });
}
