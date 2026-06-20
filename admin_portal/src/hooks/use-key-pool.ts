import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type {
  ApiKeyEntry,
  ProviderConfig,
  ProviderHealth,
  AllProvidersHealth,
  KeyStatusEvent,
  AddKeyRequest,
  UpdateKeyRequest,
  ProviderConfigRequest,
} from '@/types/key-pool';

// --- Query Keys ---

const keyPoolKeys = {
  all: ['key-pool'] as const,
  keys: (provider: string) => ['key-pool', 'keys', provider] as const,
  config: (provider: string) => ['key-pool', 'config', provider] as const,
  health: (provider: string) => ['key-pool', 'health', provider] as const,
  allHealth: () => ['key-pool', 'health'] as const,
  events: (provider: string) => ['key-pool', 'events', provider] as const,
};

// --- Queries ---

export function useProviderKeys(provider: string) {
  return useQuery({
    queryKey: keyPoolKeys.keys(provider),
    queryFn: () =>
      httpClient.get<ApiKeyEntry[]>(`/api/v1/admin/key-pool/${provider}/keys`),
    enabled: !!provider,
    retry: 1,
  });
}

export function useProviderConfig(provider: string) {
  return useQuery({
    queryKey: keyPoolKeys.config(provider),
    queryFn: () =>
      httpClient.get<ProviderConfig>(`/api/v1/admin/key-pool/${provider}/config`),
    enabled: !!provider,
  });
}

export function useProviderHealth(provider: string) {
  return useQuery({
    queryKey: keyPoolKeys.health(provider),
    queryFn: () =>
      httpClient.get<ProviderHealth>(`/api/v1/admin/key-pool/${provider}/health`),
    enabled: !!provider,
    refetchInterval: 5000,
  });
}

export function useAllProvidersHealth() {
  return useQuery({
    queryKey: keyPoolKeys.allHealth(),
    queryFn: () =>
      httpClient.get<AllProvidersHealth>('/api/v1/admin/key-pool/health'),
    refetchInterval: 5000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

export function useProviderEvents(provider: string) {
  return useQuery({
    queryKey: keyPoolKeys.events(provider),
    queryFn: () =>
      httpClient.get<KeyStatusEvent[]>(`/api/v1/admin/key-pool/${provider}/events`),
    enabled: !!provider,
  });
}

// --- Mutations ---

export function useAddKey(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AddKeyRequest) =>
      httpClient.post<ApiKeyEntry>(`/api/v1/admin/key-pool/${provider}/keys`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.keys(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.health(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.allHealth() });
    },
  });
}

export function useUpdateKey(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { keyId: string; updates: UpdateKeyRequest }) =>
      httpClient.patch<ApiKeyEntry>(
        `/api/v1/admin/key-pool/keys/${data.keyId}`,
        data.updates,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.keys(provider) });
    },
  });
}

export function useDeleteKey(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) =>
      httpClient.delete(`/api/v1/admin/key-pool/keys/${keyId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.keys(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.health(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.allHealth() });
    },
  });
}

export function useEnableKey(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) =>
      httpClient.post(`/api/v1/admin/key-pool/keys/${keyId}/enable`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.keys(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.health(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.allHealth() });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.events(provider) });
    },
  });
}

export function useDisableKey(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) =>
      httpClient.post(`/api/v1/admin/key-pool/keys/${keyId}/disable`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.keys(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.health(provider) });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.allHealth() });
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.events(provider) });
    },
  });
}

export function useUpdateProviderConfig(provider: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProviderConfigRequest) =>
      httpClient.put<ProviderConfig>(
        `/api/v1/admin/key-pool/${provider}/config`,
        data,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keyPoolKeys.config(provider) });
    },
  });
}
