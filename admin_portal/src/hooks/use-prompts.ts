import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreatePromptRequest } from '@/types/api';
import type {
  AdminUserOwnedPrompt,
  MusicDescription,
  MusicMood,
  MusicStructure,
  PromptUsageResponse,
} from '@/types/models';

// --- Descriptions ---

export function useDescriptions() {
  return useQuery({
    queryKey: ['descriptions'],
    queryFn: () =>
      httpClient.get<MusicDescription[]>('/api/v1/prompts/descriptions'),
  });
}

export function useCreateDescription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePromptRequest) =>
      httpClient.post<MusicDescription>('/api/v1/prompts/descriptions', data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['descriptions'] }),
  });
}

export function useUserOwnedDescriptions() {
  return useQuery({
    queryKey: ['descriptions', 'user-prompts'],
    queryFn: () =>
      httpClient.get<AdminUserOwnedPrompt[]>('/api/v1/prompts/descriptions/user-prompts'),
  });
}

export function useUpdateDescription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<CreatePromptRequest> }) =>
      httpClient.put<MusicDescription>(
        `/api/v1/prompts/descriptions/${data.id}`,
        data.updates,
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['descriptions'] }),
  });
}

export function useDeleteDescription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v1/prompts/descriptions/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['descriptions'] }),
  });
}

// --- Structures ---

export function useStructures() {
  return useQuery({
    queryKey: ['structures'],
    queryFn: () =>
      httpClient.get<MusicStructure[]>('/api/v1/prompts/structures'),
  });
}

export function useCreateStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePromptRequest) =>
      httpClient.post<MusicStructure>('/api/v1/prompts/structures', data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['structures'] }),
  });
}

export function useUserOwnedStructures() {
  return useQuery({
    queryKey: ['structures', 'user-prompts'],
    queryFn: () =>
      httpClient.get<AdminUserOwnedPrompt[]>('/api/v1/prompts/structures/user-prompts'),
  });
}

export function useUpdateStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<CreatePromptRequest> }) =>
      httpClient.put<MusicStructure>(
        `/api/v1/prompts/structures/${data.id}`,
        data.updates,
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['structures'] }),
  });
}

export function useDeleteStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v1/prompts/structures/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['structures'] }),
  });
}

// --- Moods ---

export function useMoods() {
  return useQuery({
    queryKey: ['moods'],
    queryFn: () =>
      httpClient.get<MusicMood[]>('/api/v1/prompts/moods'),
  });
}

export function useCreateMood() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePromptRequest) =>
      httpClient.post<MusicMood>('/api/v1/prompts/moods', data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['moods'] }),
  });
}

export function useAdminUserMoods() {
  return useQuery({
    queryKey: ['moods', 'user-prompts'],
    queryFn: () =>
      httpClient.get<AdminUserOwnedPrompt[]>('/api/v1/prompts/moods/user-prompts'),
  });
}

export function useUpdateMood() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<CreatePromptRequest> }) =>
      httpClient.put<MusicMood>(
        `/api/v1/prompts/moods/${data.id}`,
        data.updates,
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['moods'] }),
  });
}

export function useDeleteMood() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v1/prompts/moods/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['moods'] }),
  });
}

export function useDescriptionUsage(id: string | null) {
  return useQuery({
    queryKey: ['description-usage', id],
    enabled: Boolean(id),
    queryFn: () =>
      httpClient.get<PromptUsageResponse>(`/api/v1/prompts/descriptions/${id}/usage`),
  });
}

export function useStructureUsage(id: string | null) {
  return useQuery({
    queryKey: ['structure-usage', id],
    enabled: Boolean(id),
    queryFn: () =>
      httpClient.get<PromptUsageResponse>(`/api/v1/prompts/structures/${id}/usage`),
  });
}

export function useMoodUsage(id: string | null) {
  return useQuery({
    queryKey: ['mood-usage', id],
    enabled: Boolean(id),
    queryFn: () =>
      httpClient.get<PromptUsageResponse>(`/api/v1/prompts/moods/${id}/usage`),
  });
}
