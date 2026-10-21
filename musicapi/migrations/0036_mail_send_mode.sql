-- 0036_mail_send_mode — distinguish templates that may run automatically from
-- templates a human must send.
--
-- Discount mail (a human prices and caps each offer) and seasonal mail (a dated
-- message must not keep firing on a timer) are 'manual'. Everything else may be
-- attached to an automation. Every template stays manually sendable regardless.
--
-- Apply this BEFORE docs/mail-templates/seed-musicapi.sql.

ALTER TABLE mail_templates
  ADD COLUMN IF NOT EXISTS send_mode TEXT NOT NULL DEFAULT 'auto';

-- Re-adding the CHECK separately keeps the statement idempotent.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mail_templates_send_mode_check'
  ) THEN
    ALTER TABLE mail_templates
      ADD CONSTRAINT mail_templates_send_mode_check
      CHECK (send_mode IN ('auto', 'manual'));
  END IF;
END
$$;

-- Existing rows are all auto; mark the two that must never be automatic.
UPDATE mail_templates SET send_mode = 'manual'
WHERE key IN ('discount', 'seasonal', 'pack_ladder', 'referral', 'stems_spotlight');
