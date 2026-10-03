-- 0022_user_email_subscription — Settings page email-subscription preference.
-- Applied idempotently so an adopted database is safe to migrate.

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_subscription BOOLEAN NOT NULL DEFAULT true;
