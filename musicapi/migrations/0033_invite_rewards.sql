-- 0033_invite_rewards — invite-a-friend program.
--
-- A user gets a personal invite code. When a friend signs up with that code and
-- later pays for their FIRST credit pack, both sides receive a configurable
-- reward (percentage of the purchased credits or a fixed amount). Rewards are
-- only paid once per invited account; the invite row is the idempotency guard.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS invite_code TEXT;

-- Codes are looked up on signup and must be unique across users. The partial
-- index lets existing users start with NULL and receive a code lazily.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_invite_code
  ON users (invite_code)
  WHERE invite_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inviter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  invitee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  invitee_email TEXT NOT NULL,
  -- Snapshot of the code used, so an inviter can rotate theirs later without
  -- rewriting the history of already-linked friends.
  code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'rewarded', 'skipped', 'rejected')),
  -- First paid credit-pack purchase that qualified (or would have qualified).
  qualifying_transaction_id UUID REFERENCES payment_transactions(id) ON DELETE SET NULL,
  purchased_credits INTEGER,
  inviter_reward INTEGER NOT NULL DEFAULT 0,
  invitee_reward INTEGER NOT NULL DEFAULT 0,
  invited_ip TEXT,
  rewarded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- One invite per invited account: a second signup attempt (or a retried
  -- OAuth callback) can never create a duplicate reward path.
  UNIQUE (invitee_id)
);

CREATE INDEX IF NOT EXISTS idx_invites_inviter
  ON invites (inviter_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_invites_status
  ON invites (status, created_at DESC);

-- Referral credits get their own ledger type so the user-facing billing history
-- and the admin credit ledger can distinguish them from admin adjustments.
ALTER TABLE credit_transactions
  DROP CONSTRAINT IF EXISTS credit_transactions_type_check;

ALTER TABLE credit_transactions
  ADD CONSTRAINT credit_transactions_type_check
  CHECK (type IN ('purchase', 'adjust', 'spend', 'refund', 'referral'));
