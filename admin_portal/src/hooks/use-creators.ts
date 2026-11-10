import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient, { apiClient } from '@/lib/http-client';

export type PagedResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type CreatorKycRecord = {
  user_id: string;
  legal_name: string;
  date_of_birth: string;
  country_code: string;
  id_type: string;
  id_last4: string;
  id_document_ref: string;
  selfie_ref?: string | null;
  tax_id?: string | null;
  status: 'pending' | 'verified' | 'rejected' | 'expired';
  submitted_at?: string | null;
  reviewed_at?: string | null;
  reason?: string | null;
  email?: string | null;
  user_display_name?: string | null;
  handle?: string | null;
};

export type CreatorPayoutRecord = {
  id: string;
  creator_id: string;
  period_start: string;
  period_end: string;
  amount_micros: number;
  gross_micros?: number;
  withheld_micros?: number;
  fx_rate?: number | null;
  payout_amount_minor?: number | null;
  currency: string;
  method: string;
  status: 'requested' | 'approved' | 'processing' | 'paid' | 'failed' | 'cancelled';
  requested_at?: string | null;
  approved_at?: string | null;
  paid_at?: string | null;
  payment_ref?: string | null;
  failure_reason?: string | null;
  email?: string | null;
  user_display_name?: string | null;
  handle?: string | null;
};

export function useCreatorKyc(status?: string) {
  return useQuery({
    queryKey: ['creator-kyc', status],
    queryFn: async () => {
      return httpClient.get<PagedResponse<CreatorKycRecord>>(
        '/api/v3/admin/creators/kyc',
        {
          params: {
            status: status && status !== 'all' ? status : undefined,
            limit: 100,
          },
        },
      );
    },
  });
}

export function useDecideKyc() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      userId: string;
      decision: 'approve' | 'reject';
      reason?: string;
    }) => {
      return httpClient.post(
        `/api/v3/admin/creators/kyc/${encodeURIComponent(input.userId)}/decision`,
        { decision: input.decision, reason: input.reason },
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-kyc'] });
    },
  });
}

export function useCreatorPayouts(status?: string) {
  return useQuery({
    queryKey: ['creator-payouts', status],
    queryFn: async () => {
      return httpClient.get<PagedResponse<CreatorPayoutRecord>>(
        '/api/v3/admin/creators/payouts',
        {
          params: {
            status: status && status !== 'all' ? status : undefined,
            limit: 100,
          },
        },
      );
    },
  });
}

export function useMarkPayoutPaid() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { payoutId: string; reference: string }) => {
      return httpClient.post(
        `/api/v3/admin/creators/payouts/${encodeURIComponent(input.payoutId)}/mark-paid`,
        { reference: input.reference },
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-payouts'] });
    },
  });
}

export function useKycDocumentLink() {
  return useMutation({
    mutationFn: async (input: { userId: string; kind: 'id' | 'selfie' }) => {
      const response = await apiClient.get(
        `/api/v3/admin/creators/kyc/${encodeURIComponent(input.userId)}/documents/${input.kind}`,
        { responseType: 'blob' },
      );
      return response.data as Blob;
    },
  });
}

export function useGenerateTaxStatements() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (year: number) =>
      httpClient.post<{ year: number; creators: number; generated: number }>(
        `/api/v3/admin/creators/tax/statements/generate?year=${year}`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tax-statements'] });
    },
  });
}

export function useTaxStatements(year?: number) {
  return useQuery({
    queryKey: ['tax-statements', year ?? 'all'],
    queryFn: () =>
      httpClient.get<{ items: Array<Record<string, unknown>> }>(
        '/api/v3/admin/creators/tax/statements',
        year ? { year } : undefined,
      ),
  });
}

export function useApprovePayout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payoutId: string) => {
      return httpClient.post(
        `/api/v3/admin/creators/payouts/${encodeURIComponent(payoutId)}/approve`,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-payouts'] });
    },
  });
}

export type CreatorApplicationRecord = {
  id: string;
  user_id: string;
  version: number;
  requested_tier: string;
  status: 'submitted' | 'in_review' | 'changes_requested' | 'approved' | 'rejected' | 'withdrawn';
  payload: {
    pitch?: string;
    links?: Array<{ label: string; url: string }>;
  };
  submitted_at?: string | null;
  sla_due_at?: string | null;
  reviewed_at?: string | null;
  decision_reason?: string | null;
  email?: string | null;
  user_display_name?: string | null;
  handle?: string | null;
  creator_tier?: string | null;
};

export type CreatorReleaseRecord = {
  id: string;
  creator_id: string;
  source_variant: string;
  status: string;
  metadata: {
    title?: string;
    genre?: string;
    release_type?: string;
  };
  published_at?: string | null;
  takedown_reason?: string | null;
  email?: string | null;
  user_display_name?: string | null;
  handle?: string | null;
};

export function useCreatorApplications(status?: string) {
  return useQuery({
    queryKey: ['creator-applications', status],
    queryFn: async () => {
      return httpClient.get<PagedResponse<CreatorApplicationRecord>>(
        '/api/v3/admin/creators/applications',
        {
          params: {
            status: status && status !== 'all' ? status : undefined,
            limit: 100,
          },
        },
      );
    },
  });
}

export function useDecideApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      applicationId: string;
      decision: 'approve' | 'request_changes' | 'reject';
      reason?: string;
    }) => {
      return httpClient.post(
        `/api/v3/admin/creators/applications/${encodeURIComponent(input.applicationId)}/decision`,
        { decision: input.decision, reason: input.reason },
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-applications'] });
    },
  });
}

export function useCreatorReleases(status?: string) {
  return useQuery({
    queryKey: ['creator-releases', status],
    queryFn: async () => {
      return httpClient.get<PagedResponse<CreatorReleaseRecord>>(
        '/api/v3/admin/creators/releases',
        {
          params: {
            status: status && status !== 'all' ? status : undefined,
            limit: 100,
          },
        },
      );
    },
  });
}

export function useTakedownRelease() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { releaseId: string; reason: string }) => {
      return httpClient.post(
        `/api/v3/admin/creators/releases/${encodeURIComponent(input.releaseId)}/takedown`,
        { reason: input.reason },
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-releases'] });
    },
  });
}

export type RoyaltyPeriodRecord = {
  id: string;
  period_start: string;
  period_end: string;
  pool_micros: number;
  total_weighted_streams: number;
  rate_micros: number;
  status: 'open' | 'calculated' | 'locked' | 'paid';
  calculated_at?: string | null;
  locked_at?: string | null;
};

export function useRoyaltyPeriods() {
  return useQuery({
    queryKey: ['royalty-periods'],
    queryFn: async () =>
      httpClient.get<{ items: RoyaltyPeriodRecord[] }>(
        '/api/v3/admin/creators/royalty/periods',
        { limit: 24 },
      ),
  });
}

export function useCalculateRoyalty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      period_start: string;
      period_end: string;
      pool_usd?: number;
    }) => {
      return httpClient.post('/api/v3/admin/creators/royalty/calculate', input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['royalty-periods'] });
      queryClient.invalidateQueries({ queryKey: ['creator-payouts'] });
    },
  });
}

export function useLockRoyaltyPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (periodId: string) => {
      return httpClient.post(
        `/api/v3/admin/creators/royalty/periods/${encodeURIComponent(periodId)}/lock`,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['royalty-periods'] });
    },
  });
}

export function useReleaseReserve() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (periodId: string) =>
      httpClient.post<{ released_micros: number; creators: number }>(
        `/api/v3/admin/creators/royalty/periods/${encodeURIComponent(periodId)}/release-reserve`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['royalty-periods'] });
    },
  });
}

export function useMoneyAudit(limit = 100) {
  return useQuery({
    queryKey: ['creator-money-audit', limit],
    queryFn: () =>
      httpClient.get<{
        items: Array<{
          id: string;
          action: string;
          subject_type: string;
          subject_id?: string | null;
          creator_id?: string | null;
          amount_micros?: number | null;
          detail?: Record<string, unknown> | null;
          created_at: string;
          actor_email?: string | null;
          creator_email?: string | null;
        }>;
      }>('/api/v3/admin/creators/audit', { limit }),
  });
}

export function usePayoutReconciliation() {
  return useQuery({
    queryKey: ['payout-reconciliation'],
    queryFn: () =>
      httpClient.get<{
        items: Array<Record<string, unknown>>;
        totals: {
          earned_micros: number;
          unpaid_micros: number;
          settled_micros: number;
          paid_micros: number;
          in_flight_micros: number;
          variance_micros: number;
          balanced: boolean;
        };
      }>('/api/v3/admin/creators/reconciliation'),
  });
}

export function useCreatePayoutRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { period_start: string; period_end: string; fx_rate?: number }) => {
      return httpClient.post('/api/v3/admin/creators/payouts/run', input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creator-payouts'] });
    },
  });
}

export function useExportPayoutsCsv() {
  return useMutation({
    mutationFn: async (status?: string) =>
      httpClient.get<string>('/api/v3/admin/creators/payouts/export', {
        status: status && status !== 'all' ? status : undefined,
      }),
  });
}
