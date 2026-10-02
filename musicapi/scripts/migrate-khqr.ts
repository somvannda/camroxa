import "dotenv/config";
import { pool } from "../src/db.js";

const SCHEMA_SQL = `
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

-- Also upsert KHR packs if missing
INSERT INTO credit_packs (amount, price, currency, is_active)
VALUES
  (1000, 20500, 'KHR', true),
  (5000, 102500, 'KHR', true),
  (20000, 410000, 'KHR', true),
  (100000, 2000000, 'KHR', true),
  (500000, 9500000, 'KHR', true)
ON CONFLICT DO NOTHING;
`;

async function main() {
  await pool.query(SCHEMA_SQL);
  console.log("[migrate] payment_transactions table + KHR packs ensured.");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
