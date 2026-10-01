-- 0004_payment_khqr — KHQR payment transactions.
-- (Was `scripts/migrate-khqr.ts`.) No-op on a database created from 0001.

CREATE TABLE IF NOT EXISTS payment_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  pack_id UUID REFERENCES credit_packs(id) ON DELETE SET NULL,
  credit_amount INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'KHR',
  amount NUMERIC NOT NULL,
  payment_method TEXT NOT NULL DEFAULT 'khqr',
  md5_hash TEXT UNIQUE,
  qr_string TEXT,
  deeplink TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','expired','failed','refunded')),
  api_key_target_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
  bill_number TEXT,
  error_message TEXT,
  paid_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '10 minutes',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payment_tx_user ON payment_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_tx_md5 ON payment_transactions(md5_hash);
CREATE INDEX IF NOT EXISTS idx_payment_tx_status ON payment_transactions(status);
