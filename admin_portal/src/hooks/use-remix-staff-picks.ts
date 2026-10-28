import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  RemixStaffPick,
  RemixStaffPickInput,
  RemixStaffPickListResponse,
} from '@/types/remix-staff-picks';

const keys = {
  all: ['remix-staff-picks'] as const,
};

export function useRemixStaffPicks() {
  return useQuery({
    queryKey: keys.all,
    queryFn: () => httpClient.get<RemixStaffPickListResponse>('/api/v3/admin/remix/staff-picks'),
  });
}

export function useCreateRemixStaffPick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RemixStaffPickInput) =>
      httpClient.post<RemixStaffPick>('/api/v3/admin/remix/staff-picks', input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateRemixStaffPick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<RemixStaffPickInput> }) =>
      httpClient.patch<RemixStaffPick>(`/api/v3/admin/remix/staff-picks/${id}`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useDeleteRemixStaffPick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => httpClient.delete(`/api/v3/admin/remix/staff-picks/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}
