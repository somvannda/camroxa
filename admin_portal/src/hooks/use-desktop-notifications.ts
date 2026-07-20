import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type UpdateSoftwareUpdateConfigInput = {
  version: string;
  download_url: string;
  mandatory: boolean;
  release_notes: string;
};

export type SoftwareUpdateConfig = {
  version: string;
  download_url: string;
  mandatory: boolean;
  release_notes: string;
  published_at: string | null;
  is_published?: boolean;
};

export type PublishSoftwareUpdateInput = {
  notify_desktop_users?: boolean;
  create_changelog?: boolean;
};

export type PublishSoftwareUpdateResponse = {
  recipients: number;
  version: string;
  published_at: string;
  changelog_slug?: string | null;
};

export type PublishInstallerInput = {
  release_notes?: string;
  mandatory?: boolean;
  notify_desktop_users?: boolean;
  create_changelog?: boolean;
};

export type UploadDesktopSoftwareUpdateResponse = {
  download_url: string;
  filename: string;
  size_bytes: number;
  draft_saved?: boolean;
};

export type DesktopInstallerFile = {
  filename: string;
  download_url: string;
  size_bytes: number;
  modified_at: string;
  version?: string | null;
  download_count?: number;
};

export type PushNotificationHistoryItem = {
  id: string;
  title: string;
  message: string;
  created_at: string;
  recipients: number;
};

export type SendPushNotificationInput = {
  title: string;
  message: string;
};

export type SendPushNotificationResponse = {
  recipients: number;
  title: string;
  notification_id: string;
  created_at: string;
};

export function useSoftwareUpdateConfig() {
  return useQuery({
    queryKey: ['desktop-software-update'],
    queryFn: () => httpClient.get<SoftwareUpdateConfig>('/api/v1/admin/desktop/software-update'),
  });
}

export function useUpdateSoftwareUpdateConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateSoftwareUpdateConfigInput) =>
      httpClient.put<SoftwareUpdateConfig>('/api/v1/admin/desktop/software-update', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
      queryClient.invalidateQueries({ queryKey: ['system-settings'] });
    },
  });
}

export function usePublishSoftwareUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input?: PublishSoftwareUpdateInput) =>
      httpClient.post<PublishSoftwareUpdateResponse>(
        '/api/v1/admin/desktop/software-update/publish',
        input ?? {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
      queryClient.invalidateQueries({ queryKey: ['blog-posts'] });
    },
  });
}

export function useUnpublishSoftwareUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.post<{ version: string; is_published: boolean }>(
        '/api/v1/admin/desktop/software-update/unpublish',
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
    },
  });
}

export function usePublishDesktopInstaller() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { filename: string; body: PublishInstallerInput }) =>
      httpClient.post<PublishSoftwareUpdateResponse>(
        `/api/v1/admin/desktop/software-update/installers/${encodeURIComponent(payload.filename)}/publish`,
        payload.body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
      queryClient.invalidateQueries({ queryKey: ['desktop-installers'] });
      queryClient.invalidateQueries({ queryKey: ['blog-posts'] });
    },
  });
}

export function useUploadDesktopSoftwareUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { file: File; version?: string }) => {
      const form = new FormData();
      form.append('file', payload.file);
      if (payload.version?.trim()) {
        form.append('version', payload.version.trim());
      }
      return httpClient.post<UploadDesktopSoftwareUpdateResponse>(
        '/api/v1/admin/desktop/software-update/upload',
        form,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
      queryClient.invalidateQueries({ queryKey: ['desktop-installers'] });
    },
  });
}

export function useDesktopInstallers() {
  return useQuery({
    queryKey: ['desktop-installers'],
    queryFn: () =>
      httpClient.get<{ items: DesktopInstallerFile[] }>(
        '/api/v1/admin/desktop/software-update/installers',
      ),
  });
}

export function useDeleteDesktopInstaller() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filename: string) =>
      httpClient.delete<{ status: string; filename: string }>(
        `/api/v1/admin/desktop/software-update/installers/${encodeURIComponent(filename)}`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-installers'] });
    },
  });
}

export function usePushNotificationHistory() {
  return useQuery({
    queryKey: ['desktop-push-notification-history'],
    queryFn: () =>
      httpClient.get<{ items: PushNotificationHistoryItem[] }>(
        '/api/v1/admin/desktop/push-notifications/history',
      ),
  });
}

export function useSendPushNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SendPushNotificationInput) =>
      httpClient.post<SendPushNotificationResponse>('/api/v1/admin/desktop/push-notifications', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-push-notification-history'] });
    },
  });
}
