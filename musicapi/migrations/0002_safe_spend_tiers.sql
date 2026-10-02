-- 0002_safe_spend_tiers — hourly/daily/total spend caps on API keys.
-- (Was `scripts/add-safe-spend-tiers.sql`.) No-op on a database created from
-- 0001, which already has the columns.

ALTER TABLE api_keys
  ADD COLUMN IF NOT EXISTS safe_spend_hourly INTEGER,
  ADD COLUMN IF NOT EXISTS safe_spend_daily INTEGER,
  ADD COLUMN IF NOT EXISTS safe_spend_total INTEGER;

-- Backfill the new total cap from the legacy single limit.
UPDATE api_keys
SET safe_spend_total = safe_spend_limit
WHERE safe_spend_limit IS NOT NULL AND safe_spend_total IS NULL;
