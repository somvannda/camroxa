-- 0011_chmaba_payments — ChmabaPay (KHQR / ABA PayWay) checkout support on the
-- existing `payment_transactions` table (REQUIREMENTS §3.7, real payments).
-- `payment_transactions` was built for the direct Bakong flow, so the columns
-- the provider needs (its own payment id + hosted checkout URL) are added here
-- rather than duplicated into a second table. Existing rows default to the
-- 'bakong' provider.

ALTER TABLE payment_transactions
  ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'bakong';

ALTER TABLE payment_transactions
  ADD COLUMN IF NOT EXISTS provider_payment_id TEXT;

ALTER TABLE payment_transactions
  ADD COLUMN IF NOT EXISTS checkout_url TEXT;

-- One ChmabaPay payment id maps to exactly one of our rows, so a webhook (or a
-- retried delivery) can be reconciled without trusting `reference_id` alone.
CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_tx_provider_payment
  ON payment_transactions (provider_payment_id)
  WHERE provider_payment_id IS NOT NULL;
