-- 0034_mail_core — mailing foundation for music.camxora.com.
--
-- One delivery ledger backs every outbound message (receipts, credit alerts,
-- campaigns, automations), so consent, suppression and engagement are enforced
-- in one place instead of per feature.
--
-- Tracking design: opens and clicks are recorded by THIS service through signed
-- pixel / click-redirect URLs. The provider's own open tracking is deliberately
-- not used: it would double-count when a provider also reports opens, and it
-- changes with plan settings. Provider webhooks are consumed only for delivery
-- state (delivered / bounced / complained / failed).
--
-- Spend tier is measured in PURCHASED CREDITS, not money. `payment_transactions`
-- stores KHR for KHQR checkouts and USD for card checkouts, so summing `amount`
-- across rows would rank users by currency accident rather than by value.

-- ---------------------------------------------------------------------------
-- Segmentation inputs
-- ---------------------------------------------------------------------------

-- Recency axis. Updated (throttled) by authenticated requests; `usage_logs` is
-- not a substitute because it only sees generations, not browsing/sign-in.
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;

-- Consent proof, kept separate from the mutable `email_subscription`
-- preference: `email_subscription` says "wants marketing now", this says "when
-- did they say so". Transactional mail ignores both.
ALTER TABLE users ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_last_active ON users (last_active_at DESC);

-- Backfill once so the lifecycle buckets are meaningful before the first
-- request touches a row. Guarded by IS NULL so re-running is a no-op.
UPDATE users u
SET last_active_at = GREATEST(
  u.created_at,
  COALESCE((SELECT MAX(l.created_at) FROM usage_logs l WHERE l.user_id = u.id), u.created_at)
)
WHERE u.last_active_at IS NULL;

-- ---------------------------------------------------------------------------
-- Templates
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mail_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- System templates carry a stable key so code can reference them; a NULL key
  -- means an operator-authored template. NULLs are allowed to repeat in a
  -- unique index, so the pair is only enforced for keyed rows.
  key TEXT,
  locale TEXT NOT NULL DEFAULT 'en',
  name TEXT NOT NULL,
  subject TEXT NOT NULL,
  html TEXT NOT NULL,
  text TEXT,
  -- Variable names the template expects ({{name}}, {{credits}}, …) so the
  -- admin form can flag a typo before a campaign is sent.
  vars TEXT[] NOT NULL DEFAULT '{}',
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_templates_key_locale
  ON mail_templates (key, locale)
  WHERE key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Campaigns (operator-sent, once) and automations (state-triggered, repeatable)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mail_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  template_id UUID NOT NULL REFERENCES mail_templates(id) ON DELETE RESTRICT,
  -- Segment definition (criteria JSONB) is evaluated at send time, not stored
  -- as a frozen list, so "last_active_at < now() - 30 days" stays true tomorrow.
  audience JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'scheduled', 'sending', 'paused', 'sent', 'cancelled')),
  scheduled_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  -- Snapshot taken when the send begins; a later segment drift does not change
  -- what this campaign claims to have reached.
  recipient_count INTEGER NOT NULL DEFAULT 0,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mail_campaigns_status ON mail_campaigns (status, scheduled_at);

CREATE TABLE IF NOT EXISTS mail_automations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  template_id UUID NOT NULL REFERENCES mail_templates(id) ON DELETE RESTRICT,
  -- `trigger` names the event the automation listens for (e.g. `signup`,
  -- `credits_low`, `inactive`); `audience` narrows who is eligible.
  trigger TEXT NOT NULL,
  audience JSONB NOT NULL DEFAULT '{}'::jsonb,
  delay_minutes INTEGER NOT NULL DEFAULT 0
    CHECK (delay_minutes >= 0),
  -- Don't re-mail the same user about the same journey more often than this.
  cooldown_days INTEGER NOT NULL DEFAULT 30 CHECK (cooldown_days >= 1),
  is_active BOOLEAN NOT NULL DEFAULT false,
  last_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Delivery ledger — one row per recipient attempt
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mail_sends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  kind TEXT NOT NULL
    CHECK (kind IN ('transactional', 'campaign', 'automation')),
  campaign_id UUID REFERENCES mail_campaigns(id) ON DELETE SET NULL,
  automation_id UUID REFERENCES mail_automations(id) ON DELETE SET NULL,
  template_id UUID REFERENCES mail_templates(id) ON DELETE SET NULL,
  subject TEXT NOT NULL,
  -- Rendered body is stored so a queued row survives a restart (the tracking
  -- URLs contain this row's id, so it can only be rendered after the id exists).
  html TEXT,
  text TEXT,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN (
      'queued', 'sending', 'sent', 'delivered', 'opened', 'clicked',
      'bounced', 'complained', 'failed', 'suppressed', 'skipped'
    )),
  provider_id TEXT,
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  claimed_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  first_opened_at TIMESTAMPTZ,
  last_opened_at TIMESTAMPTZ,
  first_clicked_at TIMESTAMPTZ,
  last_clicked_at TIMESTAMPTZ,
  open_count INTEGER NOT NULL DEFAULT 0,
  click_count INTEGER NOT NULL DEFAULT 0,
  -- Idempotency for automations: `<automation-key>:<user>:<cycle>` prevents a
  -- re-run of the scheduler from mailing the same person twice for one cycle.
  dedupe_key TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A campaign mails a user at most once, so re-running a send is idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_sends_campaign_user
  ON mail_sends (campaign_id, user_id)
  WHERE campaign_id IS NOT NULL AND user_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_sends_dedupe
  ON mail_sends (dedupe_key)
  WHERE dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_mail_sends_user ON mail_sends (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mail_sends_queue ON mail_sends (status, created_at)
  WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_mail_sends_provider ON mail_sends (provider_id)
  WHERE provider_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mail_sends_campaign ON mail_sends (campaign_id, status);

-- ---------------------------------------------------------------------------
-- Engagement event stream
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mail_events (
  id BIGSERIAL PRIMARY KEY,
  send_id UUID NOT NULL REFERENCES mail_sends(id) ON DELETE CASCADE,
  type TEXT NOT NULL
    CHECK (type IN (
      'delivered', 'opened', 'clicked', 'bounced', 'complained', 'failed'
    )),
  -- Clicked destination (null for opens/delivery states).
  url TEXT,
  user_agent TEXT,
  ip TEXT,
  -- Provider event id, when the event came from a webhook. Unique so a retried
  -- delivery (providers retry) cannot inflate the counters.
  provider_event_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_events_provider
  ON mail_events (provider_event_id)
  WHERE provider_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_mail_events_send ON mail_events (send_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mail_events_type ON mail_events (type, created_at DESC);

-- ---------------------------------------------------------------------------
-- Hard suppression list — checked before every send, regardless of preference
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mail_suppressions (
  email TEXT PRIMARY KEY,
  reason TEXT NOT NULL
    CHECK (reason IN ('bounce', 'complaint', 'unsubscribe', 'manual')),
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Segment view: one row per user with the axes the console filters on
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW user_value AS
WITH purchases AS (
  SELECT
    user_id,
    SUM(credit_amount)::bigint AS credits_bought,
    COUNT(*)::int AS purchase_count,
    MAX(paid_at) AS last_paid_at
  FROM payment_transactions
  WHERE status = 'paid' AND credit_amount > 0
  GROUP BY user_id
),
usage AS (
  SELECT
    user_id,
    SUM(credits_consumed)::bigint AS credits_spent,
    COUNT(*)::int AS generations,
    MAX(created_at) AS last_used_at
  FROM usage_logs
  GROUP BY user_id
)
SELECT
  u.id AS user_id,
  u.email,
  u.name,
  u.language,
  u.role,
  u.status,
  u.created_at,
  u.email_subscription,
  u.last_active_at,
  COALESCE(us.last_used_at, u.created_at) AS last_used_at,
  GREATEST(
    COALESCE(u.last_active_at, u.created_at),
    COALESCE(us.last_used_at, u.created_at)
  ) AS last_seen_at,
  COALESCE(p.credits_bought, 0) AS credits_bought,
  COALESCE(p.purchase_count, 0) AS purchase_count,
  p.last_paid_at,
  COALESCE(us.credits_spent, 0) AS credits_spent,
  COALESCE(us.generations, 0) AS generations,
  -- 10 credits = one music generation (pricing.endpoint = 'music').
  (COALESCE(p.credits_bought, 0) / 10) AS songs_bought,
  CASE
    WHEN COALESCE(p.credits_bought, 0) = 0 THEN 'never'
    WHEN p.credits_bought < 3000 THEN 'small'
    ELSE 'big'
  END AS spend_tier,
  CASE
    WHEN GREATEST(
      COALESCE(u.last_active_at, u.created_at),
      COALESCE(us.last_used_at, u.created_at)
    ) >= now() - interval '7 days' THEN 'active'
    WHEN GREATEST(
      COALESCE(u.last_active_at, u.created_at),
      COALESCE(us.last_used_at, u.created_at)
    ) >= now() - interval '30 days' THEN 'warm'
    ELSE 'dormant'
  END AS lifecycle,
  EXISTS (
    SELECT 1 FROM mail_suppressions s WHERE lower(s.email) = lower(u.email)
  ) AS suppressed
FROM users u
LEFT JOIN purchases p ON p.user_id = u.id
LEFT JOIN usage us ON us.user_id = u.id;
