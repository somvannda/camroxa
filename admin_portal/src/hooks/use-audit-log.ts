import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { PaginatedResponse, AuditLogParams } from '@/types/api';
import type { AuditEntry } from '@/types/models';

type AuditLogApiResponse = {
  entries: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export function useAuditLog(params: AuditLogParams) {
  return useQuery({
    queryKey: ['audit-log', params],
    queryFn: async (): Promise<PaginatedResponse<AuditEntry>> => {
      const response = await httpClient.get<AuditLogApiResponse>(
        '/api/v1/admin/audit-log',
        params as Record<string, unknown>,
      );

      return {
        items: response.entries,
        total: response.total,
        page: response.page,
        page_size: response.page_size,
        total_pages: response.total_pages,
      };
    },
  });
}
