import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

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
