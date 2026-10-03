-- 0023_user_credit_alert_thresholds — Settings/Dashboard credit alert thresholds.
-- Up to 3 positive credit amounts that trigger an email notification when the
-- balance falls below them. Applied idempotently.

ALTER TABLE users ADD COLUMN IF NOT EXISTS credit_alert_thresholds INTEGER[] NOT NULL DEFAULT '{}';
