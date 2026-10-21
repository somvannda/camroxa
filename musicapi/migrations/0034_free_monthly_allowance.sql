-- 0034_free_monthly_allowance — monthly scoped free credits for V6-Mini.
--
-- Every user gets a fixed allowance each calendar month (UTC). It can only pay
-- for the free model (chirp-goose / V6-Mini), never V6 or V6-WILD, and unused
-- credits expire when the next period row is minted. Purchased pack credits stay
-- on api_keys.credits and remain universal.
--
-- This replaces the earlier daily 0-credit free tier, which was never deployed.

CREATE TABLE IF NOT EXISTS monthly_allowances (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- First day of the UTC month this grant belongs to.
  period_start DATE NOT NULL,
  granted INTEGER NOT NULL CHECK (granted >= 0),
  used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
  -- Model this allowance can pay for (normalised Suno key).
  scope_model TEXT NOT NULL DEFAULT 'chirp-goose',
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, period_start)
);

-- Which part of a job's cost came from the allowance, and for which period, so
-- a failed job can refund the allowance instead of the wallet.
ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS allowance_credits INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS allowance_period DATE;

-- V6-Mini is a normally priced model again; the monthly allowance pays for it.
-- `pricing` has no unique key on (endpoint, model), so update-or-insert.
UPDATE pricing
SET credit_cost = 10
WHERE endpoint = 'music' AND model = 'chirp-goose' AND credit_cost <> 10;

INSERT INTO pricing (endpoint, model, credit_cost)
SELECT 'music', 'chirp-goose', 10
WHERE NOT EXISTS (
  SELECT 1 FROM pricing WHERE endpoint = 'music' AND model = 'chirp-goose'
);
