import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { UsageListParams } from '@/types/api';
import type { UsageFiltersResponse, UsageListResponse } from '@/types/models';

export function useUsage(params: UsageListParams) {
  return useQuery({
    queryKey: ['usage', params],
    queryFn: () =>
      httpClient.get<UsageListResponse>(
        '/api/v1/admin/usage',
        params as Record<string, unknown>,
      ),
  });
}

export function useUsageFilters() {
  return useQuery({
    queryKey: ['usage-filters'],
    queryFn: () => httpClient.get<UsageFiltersResponse>('/api/v1/admin/usage/filters'),
    staleTime: 60_000,
  });
}

export type ExportTelemetryEntry = {
  id: string;
  user_id: string;
  user_email: string;
  operation_type: string;
  track_count: number;
  completed_count: number;
  duration_ms: number | null;
  codec: string | null;
  resolution: string | null;
  fps: number | null;
  export_tier: string | null;
  speed_mode: string | null;
  hw_cpu: string | null;
  hw_gpu: string | null;
  hw_encoder: string | null;
  app_version: string | null;
  created_at: string | null;
};

export type ExportTelemetryListResponse = {
  items: ExportTelemetryEntry[];
  total: number;
};

export function useExportTelemetry(params?: { user_id?: string; operation_type?: string }) {
  return useQuery({
    queryKey: ['export-telemetry', params],
    queryFn: () =>
      httpClient.get<ExportTelemetryListResponse>(
        '/api/v1/admin/export-telemetry',
        (params ?? {}) as Record<string, unknown>,
      ),
    staleTime: 15_000,
  });
}
