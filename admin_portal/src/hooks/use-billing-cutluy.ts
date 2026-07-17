import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type CutluyBillingConfig = {
  api_base_url: string;
  payment_link_id: string;
  secret_key_configured: boolean;
  secret_key_masked: string;
  secret_source: 'database' | 'environment' | 'none' | null;
  webhook_secret_configured?: boolean;
  webhook_secret_masked?: string;
  webhook_secret_source?: 'database' | 'environment' | 'none' | null;
};

export type UpdateCutluyBillingConfigInput = {
  api_base_url: string;
  payment_link_id: string;
  secret_key?: string;
  webhook_secret?: string;
};

export function useCutluyBillingConfig() {
  return useQuery({
    queryKey: ['billing-cutluy-config'],
    queryFn: () => httpClient.get<CutluyBillingConfig>('/api/v1/admin/billing/cutluy-config'),
  });
}

export function useUpdateCutluyBillingConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateCutluyBillingConfigInput) =>
      httpClient.put<CutluyBillingConfig>('/api/v1/admin/billing/cutluy-config', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-cutluy-config'] });
      queryClient.invalidateQueries({ queryKey: ['system-settings'] });
    },
  });
}
