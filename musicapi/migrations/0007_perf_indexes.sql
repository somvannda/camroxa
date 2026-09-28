-- 0007_perf_indexes — indexes for hot-path lookups.
--
-- 1) `usage_logs.api_key_id`: the safe-spend guard runs on every API-key request
--    (see `requireKey`), summing `credits_consumed` for the key over all time,
--    the last hour, and the last day. Postgres does not auto-index FK columns,
--    so those sums seq-scan the whole table. A composite `(api_key_id,
--    created_at)` index serves all three (leading column for the all-time sum,
--    both columns for the time windows), mirroring `idx_usage_logs_user`.
--
-- 2) `credit_transactions.user_id`: FK column with no index — needed for
--    `ON DELETE CASCADE` user deletes and for per-user ledger reads.

CREATE INDEX IF NOT EXISTS idx_usage_logs_api_key ON usage_logs (api_key_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user ON credit_transactions (user_id, created_at DESC);
