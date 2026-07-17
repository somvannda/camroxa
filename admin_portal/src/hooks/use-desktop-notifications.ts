import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type SoftwareUpdateConfig = {
  version: string;
  download_url: string;
  mandatory: boolean;
  release_notes: string;
  published_at: string | null;
};

export type UpdateSoftwareUpdateConfigInput = {
  version: string;
  download_url: string;
  mandatory: boolean;
  release_notes: string;
};

export type PublishSoftwareUpdateResponse = {
  recipients: number;
  version: string;
  published_at: string;
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
    mutationFn: () =>
      httpClient.post<PublishSoftwareUpdateResponse>('/api/v1/admin/desktop/software-update/publish'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['desktop-software-update'] });
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
