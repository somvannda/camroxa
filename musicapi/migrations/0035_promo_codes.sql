-- 0035_promo_codes — single-use discount and bonus codes for mail campaigns.
--
-- A code is either:
--   percent      → the checkout price drops by `value` percent (credits unchanged)
--   credit_bonus → the price is unchanged and `value` extra credits are granted
--
-- Codes may be public (user_id NULL, limited by max_redemptions) or bound to one
-- user, which is what a campaign generates: leakage of a per-user code is
-- harmless and attribution is exact.

CREATE TABLE IF NOT EXISTS promo_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK (kind IN ('percent', 'credit_bonus')),
  -- percent: 1-99 (100 would make the charge zero, which no gateway can settle)
  -- credit_bonus: absolute credits
  value NUMERIC NOT NULL CHECK (value > 0),
  -- NULL = public code. Non-null = only this user may redeem.
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  max_redemptions INTEGER NOT NULL DEFAULT 1 CHECK (max_redemptions > 0),
  redeemed_count INTEGER NOT NULL DEFAULT 0 CHECK (redeemed_count >= 0),
  expires_at TIMESTAMPTZ,
  is_active BOOLEAN NOT NULL DEFAULT true,
  -- The campaign that produced this code, when it came from a mail send.
  campaign_id UUID REFERENCES mail_campaigns(id) ON DELETE SET NULL,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_promo_codes_user ON promo_codes (user_id);
CREATE INDEX IF NOT EXISTS idx_promo_codes_campaign ON promo_codes (campaign_id);
CREATE INDEX IF NOT EXISTS idx_promo_codes_active ON promo_codes (is_active, expires_at);

-- One row per successful redemption. The unique pair is the hard guard against
-- double-spending a single-use code, even if two payments race.
CREATE TABLE IF NOT EXISTS promo_redemptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code_id UUID NOT NULL REFERENCES promo_codes(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  payment_transaction_id UUID REFERENCES payment_transactions(id) ON DELETE SET NULL,
  discount_amount NUMERIC NOT NULL DEFAULT 0,
  credits_granted INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (code_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_promo_redemptions_user
  ON promo_redemptions (user_id, created_at DESC);

-- The discount actually taken, so revenue reporting can separate gross pack
-- price from what the customer paid without re-deriving it from the code.
ALTER TABLE payment_transactions
  ADD COLUMN IF NOT EXISTS promo_code_id UUID REFERENCES promo_codes(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS promo_discount NUMERIC NOT NULL DEFAULT 0;

-- Which code was in the message, so the Mail ledger can show it.
ALTER TABLE mail_sends
  ADD COLUMN IF NOT EXISTS promo_code_id UUID REFERENCES promo_codes(id) ON DELETE SET NULL;

-- Campaign-level recipe for per-recipient codes:
--   { "kind": "percent", "value": 20, "expiresDays": 7 }
ALTER TABLE mail_campaigns
  ADD COLUMN IF NOT EXISTS promo_preset JSONB;
