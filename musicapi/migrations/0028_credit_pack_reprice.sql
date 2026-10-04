-- 0028_credit_pack_reprice — set the USD credit-pack ladder to:
--
--   $5  -> 1,000 credits
--   $10 -> 2,300 credits
--   $20 -> 5,500 credits
--   $30 -> 8,800 credits
--
-- Replaces the 0027 ladder (which was $5/1,000, $10/2,500, $20/5,800,
-- $30/9,000). Values/price points change, so the rows are deleted and replaced
-- rather than remapped: historical transactions keep their own
-- credit_amount/amount/currency copies and `pack_id` is set NULL by the FK
-- (same as migrations 0015 and 0027).

DELETE FROM credit_packs WHERE currency = 'USD';

INSERT INTO credit_packs (amount, price, currency, is_active)
VALUES
  (1000, 5,  'USD', true),
  (2300, 10, 'USD', true),
  (5500, 20, 'USD', true),
  (8800, 30, 'USD', true);
