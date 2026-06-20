import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { CreatePromptRequest } from '@/types/api';
import type { MusicDescription, MusicStructure } from '@/types/models';

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

export function useUpdateDescription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: CreatePromptRequest }) =>
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

export function useUpdateStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: CreatePromptRequest }) =>
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
