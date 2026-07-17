import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient, { apiClient } from '@/lib/http-client';
import type {
  MarketplaceItem,
  MarketplaceItemUpdate,
  MarketplaceListResponse,
} from '@/types/marketplace';

// --- Query Keys ---

const marketplaceKeys = {
  all: ['marketplace'] as const,
  list: (page: number) => ['marketplace', 'list', page] as const,
};

// --- Queries ---

export function useMarketplaceItems(page: number = 1) {
  return useQuery({
    queryKey: marketplaceKeys.list(page),
    queryFn: () =>
      httpClient.get<MarketplaceListResponse>(
        '/api/v1/marketplace/admin/items',
        { page, page_size: 25 },
      ),
  });
}

// --- Mutations ---

export function useUploadTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post<MarketplaceItem>(
        '/api/v1/marketplace/upload',
        formData,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.all });
    },
  });
}

export function useToggleStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (newStatus: 'enabled' | 'disabled') => {
      const action = newStatus === 'enabled' ? 'enable' : 'disable';
      return httpClient.post<MarketplaceItem>(
        `/api/v1/marketplace/items/${id}/${action}`,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.all });
    },
  });
}

export function useDeleteItem(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      httpClient.delete<{ ok: boolean }>(`/api/v1/marketplace/items/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.all });
    },
  });
}

export function useUpdateItem(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: MarketplaceItemUpdate) =>
      httpClient.patch<MarketplaceItem>(
        `/api/v1/marketplace/items/${id}`,
        update,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.all });
    },
  });
}

export function useUploadPreview(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post<MarketplaceItem>(
        `/api/v1/marketplace/items/${id}/preview`,
        formData,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.all });
    },
  });
}
