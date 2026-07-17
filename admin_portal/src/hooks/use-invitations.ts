import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  CreateInvitationCodeRequest,
  UpdateInvitationCodeRequest,
  UpdateSignupModeRequest,
} from '@/types/api';
import type {
  InvitationCodeAdminItem,
  InvitationCodeCreateResponse,
  SignupModeResponse,
} from '@/types/models';

export function useSignupMode() {
  return useQuery({
    queryKey: ['signup-mode'],
    queryFn: () => httpClient.get<SignupModeResponse>('/api/v1/admin/invitations/signup-mode'),
  });
}

export function useUpdateSignupMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateSignupModeRequest) =>
      httpClient.put<SignupModeResponse>('/api/v1/admin/invitations/signup-mode', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signup-mode'] });
    },
  });
}

export function useInvitationCodes() {
  return useQuery({
    queryKey: ['invitation-codes'],
    queryFn: () => httpClient.get<InvitationCodeAdminItem[]>('/api/v1/admin/invitations'),
  });
}

export function useCreateInvitationCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateInvitationCodeRequest) =>
      httpClient.post<InvitationCodeCreateResponse>('/api/v1/admin/invitations', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitation-codes'] });
    },
  });
}

export function useUpdateInvitationCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; payload: UpdateInvitationCodeRequest }) =>
      httpClient.patch<void>(`/api/v1/admin/invitations/${data.id}`, data.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitation-codes'] });
    },
  });
}

export function useDeleteInvitationCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete<void>(`/api/v1/admin/invitations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitation-codes'] });
    },
  });
}

