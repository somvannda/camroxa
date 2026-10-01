-- 0014_pricing_corrections — repair two rows whose stored value drifted from the
-- intended one.
--
-- 1. `wav_download` is meant to cost 1 credit, but it is stored as 9.
--    Migration 0013 inserts it with a `WHERE NOT EXISTS` guard, and a row for
--    the endpoint already existed (carrying 9), so the insert was skipped and
--    the intended value never landed.
-- 2. The KHR credit packs were seeded twice, so all five render twice on
--    /pricing and /admin/pricing. Keep one row per (amount, currency), move any
--    transaction that points at a duplicate onto the survivor, then drop the
--    duplicate.

UPDATE pricing
SET credit_cost = 1
WHERE endpoint = 'wav_download' AND model IS NULL AND credit_cost <> 1;

WITH ranked AS (
  SELECT id, first_value(id) OVER (PARTITION BY amount, currency ORDER BY id) AS keeper
  FROM credit_packs
)
UPDATE payment_transactions t
SET pack_id = d.keeper
FROM ranked d
WHERE d.id <> d.keeper AND t.pack_id = d.id;

WITH ranked AS (
  SELECT id, row_number() OVER (PARTITION BY amount, currency ORDER BY id) AS rn
  FROM credit_packs
)
DELETE FROM credit_packs WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
