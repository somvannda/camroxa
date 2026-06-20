import { useQuery } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { PaginatedResponse, AuditLogParams } from '@/types/api';
import type { AuditEntry } from '@/types/models';

export function useAuditLog(params: AuditLogParams) {
  return useQuery({
    queryKey: ['audit-log', params],
    queryFn: () =>
      httpClient.get<PaginatedResponse<AuditEntry>>(
        '/api/v1/admin/audit-log',
        params as Record<string, unknown>,
      ),
  });
}
