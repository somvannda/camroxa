import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { ChannelPrompt } from '@/types/models';

export interface CreateChannelPromptRequest {
  name: string;
  content: string;
  category: string;
  genre?: string;
  match_key?: string | null;
  is_active?: boolean;
}

export function useChannelPrompts() {
  return useQuery({
    queryKey: ['channel-prompts'],
    queryFn: () =>
      httpClient.get<ChannelPrompt[]>('/api/v1/channel-prompts'),
  });
}

export function useCreateChannelPrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateChannelPromptRequest) =>
      httpClient.post<ChannelPrompt>('/api/v1/channel-prompts', data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['channel-prompts'] }),
  });
}

export function useUpdateChannelPrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; updates: Partial<CreateChannelPromptRequest> }) =>
      httpClient.put<ChannelPrompt>(
        `/api/v1/channel-prompts/${data.id}`,
        data.updates,
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['channel-prompts'] }),
  });
}

export function useDeleteChannelPrompt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.delete(`/api/v1/channel-prompts/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['channel-prompts'] }),
  });
}
