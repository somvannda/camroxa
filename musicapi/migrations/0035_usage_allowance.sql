-- 0035_usage_allowance — record how much of a job's cost came from the free
-- monthly allowance, so usage/revenue reporting can separate allowance-funded
-- work from purchased-credit spend.
--
-- `credits_consumed` stays the total net charge (0 on failure); the new column
-- is the portion of that total the allowance paid. Purchased credits are
-- `credits_consumed - allowance_credits`.

ALTER TABLE usage_logs
  ADD COLUMN IF NOT EXISTS allowance_credits INTEGER NOT NULL DEFAULT 0;
