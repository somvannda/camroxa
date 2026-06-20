import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { PaginatedResponse, CreateLicenseRequest } from '@/types/api';
import type { License } from '@/types/models';

export interface LicenseListParams {
  page?: number;
  page_size?: number;
  status?: License['status'];
}

export function useLicenses(params?: LicenseListParams) {
  return useQuery({
    queryKey: ['licenses', params],
    queryFn: () =>
      httpClient.get<PaginatedResponse<License>>(
        '/api/v1/licenses',
        params as Record<string, unknown>,
      ),
  });
}

export function useCreateLicense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateLicenseRequest) =>
      httpClient.post('/api/v1/licenses', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['licenses'] }),
  });
}

export function useAssignLicense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { id: string; user_id: string }) =>
      httpClient.post(`/api/v1/licenses/${data.id}/assign`, {
        user_id: data.user_id,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['licenses'] }),
  });
}

export function useRevokeLicense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      httpClient.post(`/api/v1/licenses/${id}/revoke`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['licenses'] }),
  });
}
