import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export interface YouTubeOAuthApp {
  id: string;
  name: string;
  client_id: string;
  is_default: boolean;
  has_client_secret: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface YouTubeOAuthAppsResponse {
  apps: YouTubeOAuthApp[];
}

export function useYouTubeOAuthApps() {
  return useQuery({
    queryKey: ['youtube-oauth-apps'],
    queryFn: () => httpClient.get<YouTubeOAuthAppsResponse>('/api/v3/admin/youtube-oauth-apps'),
  });
}

export function useCreateYouTubeOAuthApp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      client_id: string;
      client_secret: string;
      is_default: boolean;
    }) => httpClient.post<YouTubeOAuthApp>('/api/v3/admin/youtube-oauth-apps', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['youtube-oauth-apps'] }),
  });
}

export function useUpdateYouTubeOAuthApp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      id: string;
      name?: string;
      client_id?: string;
      client_secret?: string;
      is_default?: boolean;
    }) =>
      httpClient.patch<YouTubeOAuthApp>(`/api/v3/admin/youtube-oauth-apps/${data.id}`, {
        name: data.name,
        client_id: data.client_id,
        client_secret: data.client_secret,
        is_default: data.is_default,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['youtube-oauth-apps'] }),
  });
}

export function useDeleteYouTubeOAuthApp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<{ message: string }>(`/api/v3/admin/youtube-oauth-apps/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['youtube-oauth-apps'] }),
  });
}
