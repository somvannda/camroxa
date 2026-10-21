# Platform mail — design and rollout

Status: **design + schema, not implemented.**
Scope: mailing for the legacy/platform stack — admin UI at `admin.camxora.com`, customers on
`music.camxora.com`, data in `camxora_platform`, served by `platform_api` (FastAPI).

The `musicapi` implementation stays exactly as deployed. This is a second, independent
system against a different database; the two never share a suppression list, a ledger or
a scheduler.

## Why it cannot reuse the musicapi code

| | `musicapi` (done) | platform (this doc) |
|---|---|---|
| Language | TypeScript / Fastify | Python / FastAPI |
| Database | `sunoapi` | `camxora_platform` |
| Users | 24 (all created in 30d) | 172 (34 in 30d) |
| Overlap | 5 emails shared | — |
| Balance | `api_keys.credits` (pooled) | `credit_wallets.balance` |
| Purchases | `payment_transactions` | `billing_payments` |
| Pricing | `pricing` + `credit_packs` | `credit_pricing` + `credit_packs` |

Only 5 of 24 emails exist on both sides, so this is genuinely a second audience.

## Decisions

1. **Reuse the existing redeem-code system for discounts.** `platform_api/services/redeem_code_service.py`
   already supports `discount_percentage`, `discount_amount` and `credit_grant`. Do **not** add a
   `promo_codes` table. Mail only needs to *generate and embed* codes; redemption already works.
2. **Do not reuse `services/email_service.py` for bulk.** It is a blocking `smtplib` sender used for
   verification codes. Campaigns need queueing, pacing, suppression and delivery state, which is what
   Resend + a ledger gives us. Transactional mail can stay on SMTP initially.
3. **Own serving paths.** `mail.camxora.com` already proxies `/mail/*` to `musicapi`. Platform mail
   therefore lives under `/api/mail/*` (matching the `/api/` convention of this stack) so tokens from
   the two systems can never be confused:
   - `https://mail.camxora.com/api/mail/o/{token}.gif` — open pixel
   - `https://mail.camxora.com/api/mail/c/{token}` — click redirect
   - `https://mail.camxora.com/api/mail/u/{token}` — unsubscribe
   - `https://mail.camxora.com/api/mail/webhook/resend` — Resend delivery events
   Both systems subscribe to the same Resend account; each ignores events whose message id it does
   not know, so one endpoint per system is safe.
4. **Segments from wallet + billing, not from credits bought.** The platform has a real wallet
   (`credit_wallets.balance`) and an explicit purchase record (`billing_payments.status='paid'`),
   so recency × spend is exact rather than derived from ledger rows.

## Schema (apply as one Alembic revision)

```sql
-- Recency + consent, mirroring what musicapi already has.
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_subscription BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at DESC);

CREATE TABLE mail_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT,
  locale TEXT NOT NULL DEFAULT 'en',
  name TEXT NOT NULL,
  subject TEXT NOT NULL,
  html TEXT NOT NULL,
  text TEXT,
  vars TEXT[] NOT NULL DEFAULT '{}',
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_mail_templates_key_locale ON mail_templates (key, locale) WHERE key IS NOT NULL;

CREATE TABLE mail_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  template_id UUID NOT NULL REFERENCES mail_templates(id) ON DELETE RESTRICT,
  audience JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','scheduled','sending','paused','sent','cancelled')),
  scheduled_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  recipient_count INTEGER NOT NULL DEFAULT 0,
  -- Redeem-code generation recipe; NULL means this campaign sends no code.
  redeem_reward JSONB,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mail_automations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  template_id UUID NOT NULL REFERENCES mail_templates(id) ON DELETE RESTRICT,
  trigger TEXT NOT NULL,
  audience JSONB NOT NULL DEFAULT '{}'::jsonb,
  delay_minutes INTEGER NOT NULL DEFAULT 0 CHECK (delay_minutes >= 0),
  cooldown_days INTEGER NOT NULL DEFAULT 30 CHECK (cooldown_days >= 1),
  is_active BOOLEAN NOT NULL DEFAULT false,
  last_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mail_sends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('transactional','campaign','automation')),
  campaign_id UUID REFERENCES mail_campaigns(id) ON DELETE SET NULL,
  automation_id UUID REFERENCES mail_automations(id) ON DELETE SET NULL,
  template_id UUID REFERENCES mail_templates(id) ON DELETE SET NULL,
  subject TEXT NOT NULL,
  html TEXT,
  text TEXT,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','sending','sent','delivered','opened','clicked',
                      'bounced','complained','failed','suppressed','skipped')),
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
  dedupe_key TEXT,
  -- The redeem code embedded in this message, when the campaign generated one.
  redeem_code_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_mail_sends_campaign_user ON mail_sends (campaign_id, user_id)
  WHERE campaign_id IS NOT NULL AND user_id IS NOT NULL;
CREATE UNIQUE INDEX uq_mail_sends_dedupe ON mail_sends (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ix_mail_sends_user ON mail_sends (user_id, created_at DESC);
CREATE INDEX ix_mail_sends_queue ON mail_sends (status, created_at) WHERE status = 'queued';
CREATE INDEX ix_mail_sends_provider ON mail_sends (provider_id) WHERE provider_id IS NOT NULL;

CREATE TABLE mail_events (
  id BIGSERIAL PRIMARY KEY,
  send_id UUID NOT NULL REFERENCES mail_sends(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('delivered','opened','clicked','bounced','complained','failed')),
  url TEXT,
  user_agent TEXT,
  ip TEXT,
  provider_event_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_mail_events_provider ON mail_events (provider_event_id)
  WHERE provider_event_id IS NOT NULL;
CREATE INDEX ix_mail_events_send ON mail_events (send_id, created_at);

CREATE TABLE mail_suppressions (
  email TEXT PRIMARY KEY,
  reason TEXT NOT NULL CHECK (reason IN ('bounce','complaint','unsubscribe','manual')),
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Segment view: recency x spend, computed from the platform's own wallet/billing.
CREATE OR REPLACE VIEW user_mail_value AS
WITH paid AS (
  SELECT user_id,
         SUM(amount_cents)::bigint AS paid_cents,
         COUNT(*)::int AS payment_count,
         MAX(COALESCE(approved_at, fulfilled_at, created_at)) AS last_paid_at
  FROM billing_payments
  WHERE status = 'paid'
  GROUP BY user_id
),
spend AS (
  SELECT user_id, SUM(amount)::bigint AS credits_spent, MAX(created_at) AS last_spend_at
  FROM credit_transactions
  WHERE direction = 'debit'
  GROUP BY user_id
)
SELECT
  u.id AS user_id,
  u.email,
  u.display_name,
  u.status,
  u.role,
  u.created_at,
  u.email_subscription,
  u.last_active_at,
  COALESCE(w.balance, 0) AS balance,
  COALESCE(p.paid_cents, 0) AS paid_cents,
  COALESCE(p.payment_count, 0) AS payment_count,
  p.last_paid_at,
  COALESCE(s.credits_spent, 0) AS credits_spent,
  GREATEST(COALESCE(u.last_active_at, u.created_at), COALESCE(s.last_spend_at, u.created_at)) AS last_seen_at,
  CASE WHEN COALESCE(p.paid_cents, 0) = 0 THEN 'never'
       WHEN p.paid_cents < 2000 THEN 'small'
       ELSE 'big' END AS spend_tier,
  CASE WHEN GREATEST(COALESCE(u.last_active_at, u.created_at), COALESCE(s.last_spend_at, u.created_at))
            >= now() - interval '7 days' THEN 'active'
       WHEN GREATEST(COALESCE(u.last_active_at, u.created_at), COALESCE(s.last_spend_at, u.created_at))
            >= now() - interval '30 days' THEN 'warm'
       ELSE 'dormant' END AS lifecycle,
  EXISTS (SELECT 1 FROM mail_suppressions ms WHERE lower(ms.email) = lower(u.email)) AS suppressed
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN paid p ON p.user_id = u.id
LEFT JOIN spend s ON s.user_id = u.id
WHERE u.deleted_at IS NULL;
```

Thresholds: `small` = under $20 of lifetime payments, matching the pack ladder's first rung.
`direction = 'debit'` is the spend side of `credit_transactions`; confirm the exact vocabulary
before applying.

## Endpoints (`routers/mail.py`, mounted on v1 + v3)

```
POST /mail/webhook/resend          public, Svix signature
GET  /mail/o/{token}.gif           public, 1x1 pixel
GET  /mail/c/{token}               public, 302 to signed destination
GET  /mail/u/{token}               public, unsubscribe page
POST /mail/u/{token}               RFC 8058 one-click

GET  /mail/templates               admin
POST /mail/templates               admin
PUT  /mail/templates/{id}          admin
GET  /mail/segments                admin, preset counts
POST /mail/audience/count          admin, live count
GET  /mail/campaigns               admin
POST /mail/campaigns               admin
POST /mail/campaigns/{id}/send     admin, queues rows
POST /mail/campaigns/{id}/test     admin, sends one
GET  /mail/deliveries              admin, ledger + stats
GET  /mail/suppressions            admin
POST /mail/suppressions            admin
GET  /mail/automations             admin
POST /mail/automations             admin
PUT  /mail/automations/{id}        admin
```

## Scheduling

`platform_api` runs a worker (`worker.py`). The queue drain and the automation evaluator belong
there, not in a request handler: claim with `FOR UPDATE SKIP LOCKED`, pace to
`MAIL_RATE_PER_SECOND`, and re-queue with attempts so a restart resumes.

## Admin UI

`admin_portal/src/pages/mail/` with the same five surfaces as the musicapi console
(deliveries, templates, campaigns, automations, suppressions), calling `/api/v3/mail/*`.
Register the route and add the nav item in the portal shell.

## Rollout

1. Alembic revision on the server (revision files are not tracked in this repo, so it must be
   generated where the chain lives — do not invent a `down_revision`).
2. `services/mail/` in `platform_api`: Resend client, token signing, renderer, segment builder.
3. `routers/mail.py` + wiring in `main.py` (v1 and v3).
4. Worker loop for the queue and automations.
5. nginx: `location /api/mail/ { proxy_pass http://127.0.0.1:8100; }` on `mail.camxora.com`.
   `/api/` already points there for the other hosts; this makes it explicit for the mail host.
6. Resend: add a second webhook endpoint pointing at `/api/mail/webhook/resend`.
7. Admin UI, then one test send, then a single campaign to `Active, never paid`.
