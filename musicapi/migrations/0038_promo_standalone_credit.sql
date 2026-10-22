-- 0038_promo_standalone_credit — a code that tops up a balance with no purchase.
--
-- 0035 shipped two checkout-only kinds:
--   percent      → the pack price drops, credits unchanged
--   credit_bonus → extra credits attached to a pack purchase
-- Neither can be claimed without paying, so a "here are 500 credits on us" code
-- had nowhere to go. `credit` closes that gap: redeeming it credits the user's
-- balance directly from the dashboard Redeem page.
--
-- A standalone claim is a promo_redemptions row whose payment_transaction_id is
-- NULL — that is what distinguishes it from a checkout redemption.

ALTER TABLE promo_codes DROP CONSTRAINT IF EXISTS promo_codes_kind_check;

ALTER TABLE promo_codes
  ADD CONSTRAINT promo_codes_kind_check
  CHECK (kind IN ('percent', 'credit_bonus', 'credit'));

-- A standalone code is a grant, not a purchase, so it gets its own ledger type:
-- the user's credit history and the admin ledger can tell it apart from an admin
-- adjustment or a referral reward.
ALTER TABLE credit_transactions DROP CONSTRAINT IF EXISTS credit_transactions_type_check;

ALTER TABLE credit_transactions
  ADD CONSTRAINT credit_transactions_type_check
  CHECK (type IN ('purchase', 'adjust', 'spend', 'refund', 'referral', 'promo'));
