-- 0036_allowance_no_carryover — harden the monthly allowance against accrual.
--
-- Each month has its own `monthly_allowances` row keyed by (user_id,
-- period_start). Charging and `GET /me/billing` read only the current month's
-- row, so unused credits are never carried into the next grant: a free user's
-- spendable balance is always at most that month's grant (50 by default).
--
-- This constraint ensures a bug or manual edit can never mark more credits used
-- than were granted; combined with the period-keyed rows it caps the balance.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'monthly_allowances_used_within_grant'
  ) THEN
    ALTER TABLE monthly_allowances
      ADD CONSTRAINT monthly_allowances_used_within_grant CHECK (used <= granted);
  END IF;
END $$;
