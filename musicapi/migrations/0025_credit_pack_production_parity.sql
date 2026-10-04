-- 0025_credit_pack_production_parity — align the credit-pack ladder and the
-- headline `music` cost with the live production/sandbox values so local,
-- sandbox and production all quote the same prices.
--
-- Live production (musicapi.camxora.com) and sandbox
-- (musicapi.sandbox.camxora.com) serve:
--
--   $10  ->  2,500 credits
--   $30  -> 10,000 credits
--   $60  -> 20,000 credits
--   $100 -> 33,000 credits
--   music = 10 credits per generation (2 songs)
--
-- Migration 0015 had rebalanced these to 3,500/11,000/23,000/40,000 with
-- music = 15, but production was never moved. This migration converges the repo
-- and local dev onto what production actually charges. It is written to be a
-- no-op on an environment already at parity, so it is safe to run on sandbox
-- and production: existing rows keep their id (so historical
-- `payment_transactions.pack_id` links survive).

-- 1. Headline music cost.
UPDATE pricing
SET credit_cost = 10
WHERE endpoint = 'music' AND model IS NULL AND credit_cost <> 10;

-- 2. Drop any USD pack that is not part of the production ladder.
DELETE FROM credit_packs
WHERE currency = 'USD'
  AND amount NOT IN (2500, 10000, 20000, 33000);

-- 3. Correct the price/active flag of any ladder rung that drifted.
UPDATE credit_packs p
SET price = v.price,
    is_active = true
FROM (VALUES (2500, 10), (10000, 30), (20000, 60), (33000, 100)) AS v(amount, price)
WHERE p.currency = 'USD'
  AND p.amount = v.amount
  AND (p.price <> v.price OR NOT p.is_active);

-- 4. Add any missing ladder rung.
INSERT INTO credit_packs (amount, price, currency, is_active)
SELECT v.amount, v.price, 'USD', true
FROM (VALUES (2500, 10), (10000, 30), (20000, 60), (33000, 100)) AS v(amount, price)
WHERE NOT EXISTS (
  SELECT 1 FROM credit_packs p
  WHERE p.currency = 'USD' AND p.amount = v.amount
);
