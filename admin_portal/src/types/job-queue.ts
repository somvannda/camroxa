export interface JobQueueOldestClaimable {
  id: string;
  job_type: string;
  age_seconds: number;
  created_at: string | null;
}

export interface JobQueueBusyWorker {
  worker_id: string;
  running_jobs: number;
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
