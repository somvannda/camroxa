-- 0015_pricing_rebalance — move the headline price to a Suno-parity credit
-- value, and re-denominate the packs as a 4-tier volume ladder.
--
-- `music` goes from 9 to 15 credits. Giving a generation 1.5x as many credits
-- lets 1 credit be worth roughly a Suno credit (~$0.003 at the entry tier)
-- while the generation still costs the customer $0.045 -- the same as before,
-- so revenue per song is unchanged.
--
-- Each larger pack buys credits at a better rate than the one below it:
--
--   $10   ->  3,500 cr   (350 cr/$)
--   $30   -> 11,000 cr   (367 cr/$)
--   $60   -> 23,000 cr   (383 cr/$)
--   $100  -> 40,000 cr   (400 cr/$)
--
-- `credit_packs` has no unique key, so the old USD rows are deleted rather than
-- upserted. `payment_transactions.pack_id` is ON DELETE SET NULL and no
-- historical transaction maps onto a new tier, so any such reference is
-- cleared rather than re-pointed.

UPDATE pricing
SET credit_cost = 15
WHERE endpoint = 'music' AND model IS NULL AND credit_cost <> 15;

DELETE FROM credit_packs WHERE currency = 'USD';

INSERT INTO credit_packs (amount, price, currency, is_active)
VALUES
  (3500, 10, 'USD', true),
  (11000, 30, 'USD', true),
  (23000, 60, 'USD', true),
  (40000, 100, 'USD', true);
