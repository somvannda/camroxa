import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  SignupDomainAccountsResponse,
  SignupDomainActionRequest,
  SignupDomainActionResponse,
  SignupDomainGuardConfig,
  SignupDomainGuardPayload,
} from '@/types/signup-domain-guard';

const sgKeys = {
  all: ['signup-domain-guard'] as const,
  config: () => ['signup-domain-guard', 'config'] as const,
  accounts: (domain: string) => ['signup-domain-guard', 'accounts', domain] as const,
};

const SG_BASE = '/api/v1/admin/signup-domain-guard';

export function useSignupDomainGuard() {
  return useQuery({
    queryKey: sgKeys.config(),
    queryFn: () => httpClient.get<SignupDomainGuardConfig>(SG_BASE),
  });
}

export function useUpdateSignupDomainGuard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SignupDomainGuardPayload) =>
      httpClient.put<SignupDomainGuardConfig>(SG_BASE, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sgKeys.all });
    },
  });
}

export function useSignupDomainAccounts(domain: string | null) {
  const enabled = Boolean(domain && domain.trim().includes('.'));
  return useQuery({
    queryKey: sgKeys.accounts(domain ?? ''),
    queryFn: () =>
      httpClient.get<SignupDomainAccountsResponse>(
        `${SG_BASE}/accounts?domain=${encodeURIComponent(domain ?? '')}`,
      ),
    enabled,
  });
}

export function useSignupDomainAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: SignupDomainActionRequest) =>
      httpClient.post<SignupDomainActionResponse>(`${SG_BASE}/domain-action`, request),
    onSuccess: (_result, request) => {
      queryClient.invalidateQueries({ queryKey: sgKeys.all });
      queryClient.invalidateQueries({ queryKey: sgKeys.accounts(request.domain) });
    },
  });
}
