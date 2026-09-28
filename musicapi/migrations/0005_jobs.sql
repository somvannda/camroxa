-- 0005_jobs — durable job store (task 2.1, branch `feat/musicapi-job-persistence`).
-- Defined here so the runner is the single source of truth for schema once the
-- Phase-2 branches are integrated; harmless if the branch's own
-- `scripts/migrate-jobs.ts` was already run (identical, idempotent DDL).

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','streaming','complete','error')),
  account_id TEXT,
  result_json JSONB,
  error TEXT,
  callback_url TEXT,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
  endpoint TEXT,
  model TEXT,
  prompt TEXT,
  credits INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
