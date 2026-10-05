-- 0029_admin_perf_indexes — indexes backing the admin console's list and
-- analytics queries. The new read-only views (payments, credit ledger, jobs,
-- logs, analytics) all order by `created_at DESC` and several filter by
-- `status`; without these, Postgres sorts/seq-scans the whole table.
--
-- Idempotent (IF NOT EXISTS), so it is a no-op where an equivalent index exists.

-- Admin-wide usage logs + analytics: order by time, optionally filter by status.
CREATE INDEX IF NOT EXISTS idx_usage_logs_created
  ON usage_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_status_created
  ON usage_logs (status, created_at DESC);

-- Jobs console: order by time, optionally filter by status.
CREATE INDEX IF NOT EXISTS idx_jobs_status_created
  ON jobs (status, created_at DESC);

-- Payments console: order by time.
CREATE INDEX IF NOT EXISTS idx_payment_tx_created
  ON payment_transactions (created_at DESC);

-- Credit ledger: order by time (0007 added (user_id, created_at); this serves
-- the global, unfiltered view).
CREATE INDEX IF NOT EXISTS idx_credit_tx_created
  ON credit_transactions (created_at DESC);
