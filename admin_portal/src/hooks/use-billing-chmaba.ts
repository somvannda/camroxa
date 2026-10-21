import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type ChmabaBillingConfig = {
  api_base_url: string;
  store_id: string;
  api_key_configured: boolean;
  api_key_masked: string;
  api_key_source: 'database' | 'environment' | 'none' | null;
  store_source: 'database' | 'environment' | 'none' | null;
  webhook_secret_configured: boolean;
  webhook_secret_masked: string;
  webhook_secret_source: 'database' | 'environment' | 'none' | null;
  ready: boolean;
};

export type UpdateChmabaBillingConfigInput = {
  api_base_url: string;
  store_id: string;
  api_key?: string;
  webhook_secret?: string;
};

export function useChmabaBillingConfig() {
  return useQuery({
    queryKey: ['billing-chmaba-config'],
    queryFn: () => httpClient.get<ChmabaBillingConfig>('/api/v3/admin/billing/chmaba-config'),
  });
}

export function useUpdateChmabaBillingConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateChmabaBillingConfigInput) =>
      httpClient.put<ChmabaBillingConfig>('/api/v3/admin/billing/chmaba-config', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-chmaba-config'] });
      queryClient.invalidateQueries({ queryKey: ['system-settings'] });
    },
  });
}
