import { useQuery } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  ImageJobFailuresResponse,
  JobQueueJobsParams,
  JobQueueJobsResponse,
  JobQueueMetricsResponse,
} from '@/types/job-queue';

export const jobQueueKeys = {
  all: ['job-queue'] as const,
  metrics: ['job-queue', 'metrics'] as const,
  jobs: (params: JobQueueJobsParams) => ['job-queue', 'jobs', params] as const,
  imageFailures: (hours: number) => ['job-queue', 'image-failures', hours] as const,
};

export function useJobQueueMetrics() {
  return useQuery({
    queryKey: jobQueueKeys.metrics,
    queryFn: () =>
      httpClient.get<JobQueueMetricsResponse>('/api/v1/admin/job-queue/metrics'),
    refetchInterval: 8_000,
    refetchIntervalInBackground: false,
  });
}

export function useJobQueueJobs(params: JobQueueJobsParams) {
  return useQuery({
    queryKey: jobQueueKeys.jobs(params),
    queryFn: () => {
      const query: Record<string, unknown> = {
        limit: params.limit ?? 50,
      };
      if (params.status) query.status = params.status;
      if (params.job_type) query.job_type = params.job_type;
      if (params.user) query.user = params.user;
      return httpClient.get<JobQueueJobsResponse>(
        '/api/v1/admin/job-queue/jobs',
        query,
      );
    },
    refetchInterval: 8_000,
    refetchIntervalInBackground: false,
  });
}

export function useRecentImageFailures(hours = 24) {
  return useQuery({
    queryKey: jobQueueKeys.imageFailures(hours),
    queryFn: () =>
      httpClient.get<ImageJobFailuresResponse>(
        '/api/v1/admin/job-queue/image-failures',
        { hours, limit: 30 },
      ),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  });
}
