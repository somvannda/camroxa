-- 0018_pricing_integrity — make the pricing table trustworthy.
--
-- 1. `wav_download` (the paid WAV byte download via GET /me/download) costs 3
--    credits. Migrations 0013 and 0014 both wrote 1, so a database created from
--    scratch disagreed with the running one; `DEFAULT_COSTS` also said 1. 3 is
--    authoritative and this migration is the final word for existing databases.
-- 2. `pricing` has no unique key on (endpoint, model), so an admin edit that
--    re-points a row's key could leave two rows for the same pair and `costFor`
--    would pick an arbitrary/stale one. Collapse any such pair to one survivor.
-- 3. Add a CHECK so a negative cost can never be stored. Together with the API
--    validation on POST/PUT /admin/pricing this closes the "negative credit_cost
--    mints credits through `charge`" hole at the storage layer too.
--
-- `pricing` has no unique constraint, so this uses UPDATE/DELETE, never
-- `ON CONFLICT`.

UPDATE pricing
SET credit_cost = 3
WHERE endpoint = 'wav_download' AND model IS NULL AND credit_cost <> 3;

-- Floor any bogus negative cost before the CHECK below is validated.
UPDATE pricing SET credit_cost = 0 WHERE credit_cost < 0;

-- Keep the earliest row per (endpoint, model) and drop the rest.
WITH ranked AS (
  SELECT id, first_value(id) OVER (PARTITION BY endpoint, model ORDER BY id) AS keeper
  FROM pricing
)
DELETE FROM pricing WHERE id IN (SELECT id FROM ranked WHERE id <> keeper);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'pricing_credit_cost_nonneg'
  ) THEN
    ALTER TABLE pricing
      ADD CONSTRAINT pricing_credit_cost_nonneg CHECK (credit_cost >= 0);
  END IF;
END $$;
