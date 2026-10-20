"""Mail ledger for the platform stack (admin.camxora.com / music.camxora.com).

Adds the delivery ledger, templates, campaigns, automations, engagement events and
the hard suppression list for the platform's own mailing system. This is separate
from the musicapi mail tables: that service owns ``sunoapi`` and its own audience,
while this one owns ``camxora_platform``. Only 5 of 24+172 emails overlap, so the
two are different audiences and must not share a suppression list.

Segments are computed from ``credit_wallets.balance`` and ``billing_payments``,
so recency x spend is exact rather than reconstructed from ledger rows. The
vocabularies were verified against production: ``credit_transactions.direction``
uses ``debit`` for spend, and ``billing_payments.status`` uses ``paid``.

Revision ID: 140_platform_mail
Revises: 139_referral_program
Create Date: 2026-10-20
"""

from alembic import op

revision = "140_platform_mail"
down_revision = "139_referral_program"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- segmentation inputs -------------------------------------------------
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS email_subscription BOOLEAN NOT NULL DEFAULT true,
            ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_users_last_active_at
            ON users (last_active_at DESC)
        """
    )
    # One-time backfill so lifecycle buckets are meaningful before the first
    # authenticated request touches a row.
    op.execute(
        """
        UPDATE users u
        SET last_active_at = GREATEST(
            u.created_at,
            COALESCE((SELECT MAX(t.created_at) FROM credit_transactions t
                      WHERE t.user_id = u.id), u.created_at)
        )
        WHERE u.last_active_at IS NULL
        """
    )

    # --- templates -----------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_templates (
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
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_templates_key_locale
            ON mail_templates (key, locale)
            WHERE key IS NOT NULL
        """
    )

    # --- campaigns and automations ------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_campaigns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            template_id UUID NOT NULL REFERENCES mail_templates(id) ON DELETE RESTRICT,
            audience JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'scheduled', 'sending', 'paused', 'sent', 'cancelled')),
            scheduled_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            recipient_count INTEGER NOT NULL DEFAULT 0,
            -- Redeem-code recipe, reusing the existing redeem-code system rather
            -- than introducing a second discount concept.
            redeem_reward JSONB,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mail_campaigns_status
            ON mail_campaigns (status, scheduled_at)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_automations (
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
        )
        """
    )

    # --- delivery ledger -----------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_sends (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('transactional', 'campaign', 'automation')),
            campaign_id UUID REFERENCES mail_campaigns(id) ON DELETE SET NULL,
            automation_id UUID REFERENCES mail_automations(id) ON DELETE SET NULL,
            template_id UUID REFERENCES mail_templates(id) ON DELETE SET NULL,
            subject TEXT NOT NULL,
            html TEXT,
            text TEXT,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'sending', 'sent', 'delivered', 'opened', 'clicked',
                                  'bounced', 'complained', 'failed', 'suppressed', 'skipped')),
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
            redeem_code_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Re-running a send must not mail anyone twice.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_sends_campaign_user
            ON mail_sends (campaign_id, user_id)
            WHERE campaign_id IS NOT NULL AND user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_sends_dedupe
            ON mail_sends (dedupe_key)
            WHERE dedupe_key IS NOT NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mail_sends_user ON mail_sends (user_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mail_sends_queue
            ON mail_sends (status, created_at)
            WHERE status = 'queued'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mail_sends_provider
            ON mail_sends (provider_id)
            WHERE provider_id IS NOT NULL
        """
    )

    # --- engagement events ---------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_events (
            id BIGSERIAL PRIMARY KEY,
            send_id UUID NOT NULL REFERENCES mail_sends(id) ON DELETE CASCADE,
            type TEXT NOT NULL
                CHECK (type IN ('delivered', 'opened', 'clicked', 'bounced', 'complained', 'failed')),
            url TEXT,
            user_agent TEXT,
            ip TEXT,
            provider_event_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_events_provider
            ON mail_events (provider_event_id)
            WHERE provider_event_id IS NOT NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mail_events_send ON mail_events (send_id, created_at)"
    )

    # --- suppression ---------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_suppressions (
            email TEXT PRIMARY KEY,
            reason TEXT NOT NULL
                CHECK (reason IN ('bounce', 'complaint', 'unsubscribe', 'manual')),
            source TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # --- segment view --------------------------------------------------------
    op.execute(
        """
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
            SELECT user_id,
                   SUM(amount)::bigint AS credits_spent,
                   MAX(created_at) AS last_spend_at
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
            GREATEST(COALESCE(u.last_active_at, u.created_at),
                     COALESCE(s.last_spend_at, u.created_at)) AS last_seen_at,
            CASE WHEN COALESCE(p.paid_cents, 0) = 0 THEN 'never'
                 WHEN p.paid_cents < 2000 THEN 'small'
                 ELSE 'big' END AS spend_tier,
            CASE WHEN GREATEST(COALESCE(u.last_active_at, u.created_at),
                               COALESCE(s.last_spend_at, u.created_at))
                      >= now() - interval '7 days' THEN 'active'
                 WHEN GREATEST(COALESCE(u.last_active_at, u.created_at),
                               COALESCE(s.last_spend_at, u.created_at))
                      >= now() - interval '30 days' THEN 'warm'
                 ELSE 'dormant' END AS lifecycle,
            EXISTS (SELECT 1 FROM mail_suppressions ms
                    WHERE lower(ms.email) = lower(u.email)) AS suppressed
        FROM users u
        LEFT JOIN credit_wallets w ON w.user_id = u.id
        LEFT JOIN paid p ON p.user_id = u.id
        LEFT JOIN spend s ON s.user_id = u.id
        WHERE u.deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS user_mail_value")
    op.execute("DROP TABLE IF EXISTS mail_events")
    op.execute("DROP TABLE IF EXISTS mail_sends")
    op.execute("DROP TABLE IF EXISTS mail_automations")
    op.execute("DROP TABLE IF EXISTS mail_campaigns")
    op.execute("DROP TABLE IF EXISTS mail_templates")
    op.execute("DROP TABLE IF EXISTS mail_suppressions")
    op.execute("DROP INDEX IF EXISTS ix_users_last_active_at")
    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS last_active_at,
            DROP COLUMN IF EXISTS email_subscription,
            DROP COLUMN IF EXISTS marketing_opt_in_at
        """
    )
