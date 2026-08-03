import { useQuery } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type { JobQueueMetricsResponse } from '@/types/job-queue';

export function useJobQueueMetrics() {
  return useQuery({
    queryKey: ['job-queue', 'metrics'],
    queryFn: () =>
      httpClient.get<JobQueueMetricsResponse>('/api/v1/admin/job-queue/metrics'),
    refetchInterval: 15_000,
  });
}
