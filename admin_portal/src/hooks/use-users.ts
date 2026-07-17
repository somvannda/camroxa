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
      const resp = await httpClient.get<UsersApiResponse>('/api/v1/users', params as Record<string, unknown>);
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
      httpClient.patch<User>(`/api/v1/users/${data.id}`, data.updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useSuspendUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; reason: string }) =>
      httpClient.post(`/api/v1/users/${data.id}/suspend`, { reason: data.reason }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useReactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post(`/api/v1/users/${id}/reactivate`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v1/users/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}


export function useUserDetails(id: string) {
  return useQuery({
    queryKey: ['users', id, 'details'],
    queryFn: () => httpClient.get<UserFullDetail>(`/api/v1/users/${id}/details`),
    enabled: !!id,
  });
}

export function useChannelProfileLogoBlob(profileId: string) {
  return useQuery({
    queryKey: ['channel-profiles', profileId, 'logo-blob'],
    queryFn: async () => {
      const resp = await apiClient.get(
        `/api/v1/media/channel-profiles/${profileId}/logo`,
        { responseType: 'blob' },
      );
      return resp.data as Blob;
    },
    enabled: !!profileId,
  });
}

export function useChannelProfileCoverBlob(profileId: string, index: number) {
  return useQuery({
    queryKey: ['channel-profiles', profileId, 'cover-blob', index],
    queryFn: async () => {
      const resp = await apiClient.get(
        `/api/v1/media/channel-profiles/${profileId}/covers/${index}`,
        { responseType: 'blob' },
      );
      return resp.data as Blob;
    },
    enabled: !!profileId && index >= 0,
  });
}
