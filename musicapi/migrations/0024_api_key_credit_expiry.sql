-- 0024_api_key_credit_expiry — purchased credits are valid for 12 months from
-- the most recent grant. Enforcement lives in src/server.ts: on key access an
-- expired balance is zeroed once, and the spend statements refuse to draw on
-- expired credits even if the zeroing write was missed.

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS credits_expire_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_api_keys_credits_expire
  ON api_keys (credits_expire_at)
  WHERE credits_expire_at IS NOT NULL;
