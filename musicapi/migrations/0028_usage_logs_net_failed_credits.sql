-- 0028_usage_logs_net_failed_credits — stop counting refunded failures as spend.
--
-- `usage_logs.credits_consumed` recorded the gross charge even for a job that
-- ended in `error` and was refunded. That inflated the per-key safe-spend sums
-- (`charge` / `chargeUserKey` sum this column) and showed failed jobs as charged
-- in the dashboard. Settlement now logs net credits (0 on failure); this
-- backfills strictly-refunded failures so history and the logs UI agree.
--
-- Idempotent: after the first run the rows no longer match `credits_consumed <> 0`.
-- Rows without a matching `refund` ledger entry are deliberately left untouched.

UPDATE usage_logs ul
SET credits_consumed = 0
WHERE ul.status = 'error'
  AND ul.credits_consumed <> 0
  AND EXISTS (
    SELECT 1
    FROM credit_transactions ct
    WHERE ct.job_id::text = ul.task_id
      AND ct.type = 'refund'
  );
