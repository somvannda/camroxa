export interface JobQueueOldestClaimable {
  id: string;
  job_type: string;
  age_seconds: number;
  created_at: string | null;
}

export interface JobQueueBusyWorker {
  worker_id: string;
  running_jobs: number;
  job_types?: string[];
  user_emails?: string[];
  stages?: string[];
}

export interface JobQueueSnapshot {
  by_status: Record<string, number>;
  queued_depth: number;
  running: number;
  failed: number;
  by_type: Record<string, Record<string, number>>;
  oldest_claimable: JobQueueOldestClaimable | null;
  workers_busy: JobQueueBusyWorker[];
}

export interface ProgressLatencySnapshot {
  path: string;
  samples: number;
  p50_ms: number | null;
  p95_ms: number | null;
  max_ms: number | null;
}

export interface JobQueueMetricsResponse {
  queue: JobQueueSnapshot;
  progress_latency: ProgressLatencySnapshot;
  alerts: string[];
  note?: string;
}

export type JobQueueStatusFilter = 'running' | 'queued' | 'delayed' | 'failed';

export interface JobQueueJobRow {
  id: string;
  user_id: string;
  user_email: string;
  batch_id: string | null;
  song_id: string | null;
  job_type: string;
  stage: string;
  provider: string | null;
  status: string;
  priority: number;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  locked_by: string | null;
  locked_at: string | null;
  run_after: string | null;
  created_at: string | null;
  updated_at: string | null;
  age_seconds: number;
}

export interface JobQueueJobsResponse {
  jobs: JobQueueJobRow[];
  count: number;
}

export interface ImageJobFailureRow {
  id: string;
  user_id: string;
  user_email: string;
  batch_id: string | null;
  song_id: string | null;
  kind: string;
  channel_role: string;
  provider: string | null;
  status: string;
  attempt_count: number;
  error: string | null;
  updated_at: string | null;
  age_seconds: number;
}

export interface ImageJobFailuresResponse {
  failures: ImageJobFailureRow[];
  count: number;
  hours: number;
}

export interface JobQueueJobsParams {
  status?: JobQueueStatusFilter;
  job_type?: string;
  user?: string;
  limit?: number;
}
