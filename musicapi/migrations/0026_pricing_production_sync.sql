-- 0026_pricing_production_sync — align the seeded music price and credit-pack
-- ladder with production.
--
-- Production charges 10 credits per music generation (older seeds wrote 15) and
-- sells a 4-tier ladder at $5 / $10 / $20 / $30. Written idempotently so it is a
-- no-op on a database that already matches production.

UPDATE pricing
SET credit_cost = 10
WHERE endpoint = 'music' AND model IS NULL AND credit_cost <> 10;

-- Correct the price on any existing active USD pack.
UPDATE credit_packs SET price = 5
WHERE amount = 1000 AND currency = 'USD' AND is_active AND price <> 5;
UPDATE credit_packs SET price = 10
WHERE amount = 2300 AND currency = 'USD' AND is_active AND price <> 10;
UPDATE credit_packs SET price = 20
WHERE amount = 5500 AND currency = 'USD' AND is_active AND price <> 20;
UPDATE credit_packs SET price = 30
WHERE amount = 8800 AND currency = 'USD' AND is_active AND price <> 30;

-- Add any missing tier.
INSERT INTO credit_packs (amount, price, currency, is_active)
SELECT v.amount, v.price, 'USD', true
FROM (VALUES (1000, 5), (2300, 10), (5500, 20), (8800, 30)) AS v(amount, price)
WHERE NOT EXISTS (
  SELECT 1 FROM credit_packs cp
  WHERE cp.amount = v.amount AND cp.currency = 'USD' AND cp.is_active
);

-- Retire any active USD tier that is not part of the ladder.
UPDATE credit_packs SET is_active = false
WHERE currency = 'USD' AND is_active AND amount NOT IN (1000, 2300, 5500, 8800);
