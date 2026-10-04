-- 0027_credit_pack_relaunch — replace the USD credit-pack ladder with the new
-- $5 / $10 / $20 / $30 structure:
--
--   $5  -> 1,000 credits
--   $10 -> 2,500 credits
--   $20 -> 5,800 credits
--   $30 -> 9,000 credits
--
-- With `music` = 10 credits and 2 songs per generation this is a monotonic
-- ladder (200 / 250 / 290 / 300 credits per $1). These are new price points,
-- so the old rows are deleted and replaced rather than remapped: a transaction
-- that bought the old $30 pack must not end up attached to a differently-priced
-- row. `payment_transactions` keeps its own credit_amount/amount/currency
-- copies, so history stays accurate; its `pack_id` is set NULL by the FK
-- (same behaviour as migration 0015).

DELETE FROM credit_packs WHERE currency = 'USD';

INSERT INTO credit_packs (amount, price, currency, is_active)
VALUES
  (1000, 5,  'USD', true),
  (2500, 10, 'USD', true),
  (5800, 20, 'USD', true),
  (9000, 30, 'USD', true);
