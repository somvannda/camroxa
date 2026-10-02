-- 0006_credit_ledger — link ledger rows to jobs and make settlement idempotent
-- (task 2.3, branch `feat/musicapi-refunds-ledger`). Defined here so the runner
-- is the single source of truth for schema once the Phase-2 branches are
-- integrated; harmless if the branch's own `scripts/migrate-credit-ledger.ts`
-- was already run (identical, idempotent DDL).

ALTER TABLE credit_transactions
  ADD COLUMN IF NOT EXISTS job_id UUID;

-- A job may produce at most one `spend` and one `refund` row, so a retried
-- settlement can't double-charge or double-refund.
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_tx_job_type
  ON credit_transactions (job_id, type)
  WHERE job_id IS NOT NULL;
