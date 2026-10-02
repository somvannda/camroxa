-- 0020_champapay_gateway — ChmabaPay hosted-checkout reconciliation columns.
-- (Was `scripts/migrate-champapay.ts`.) The gateway returns its own payment id and
-- a webhook event id; both are needed to reconcile a webhook or status poll back
-- to our row without trusting `reference_id` alone — `src/server.ts` fulfills via
-- `WHERE gateway_payment_id = $1` and records `webhook_event_id`. A database built
-- from 0001–0019 alone lacked these, so a fresh install would break the ChmabaPay
-- flow. Idempotent: a no-op where the ad-hoc script already ran.

ALTER TABLE payment_transactions
  ADD COLUMN IF NOT EXISTS gateway_payment_id TEXT,
  ADD COLUMN IF NOT EXISTS webhook_event_id TEXT;

CREATE INDEX IF NOT EXISTS idx_payment_tx_gateway ON payment_transactions (gateway_payment_id);
