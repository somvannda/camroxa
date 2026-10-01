-- 0021_app_settings_reconcile — the shared `sunoapi` database carried a legacy
-- key/value `app_settings` table from the archived python/electron app, so
-- migration 0010's `CREATE TABLE IF NOT EXISTS` was a silent no-op and the
-- operator-settings code (REQUIREMENTS §4.10) could not store its JSONB
-- documents. Reconcile the table to the 0010 shape: add the missing `updated_by`
-- column, coerce a text `value` to JSONB (legacy plain-string rows become JSON
-- strings, which keeps keys such as `chmaba_webhook_secret` intact and out of the
-- way of the `brand`/`alerts` documents), and enforce the 0010 constraints. Every
-- step is guarded so this is a no-op on a database where 0010 already created the
-- table correctly.

ALTER TABLE app_settings
  ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES users(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'app_settings'
       AND column_name = 'value'
       AND data_type <> 'jsonb'
  ) THEN
    ALTER TABLE app_settings
      ALTER COLUMN value TYPE JSONB USING to_jsonb(value);
  END IF;
END $$;

UPDATE app_settings SET value = 'null'::jsonb WHERE value IS NULL;

ALTER TABLE app_settings ALTER COLUMN value SET NOT NULL;
ALTER TABLE app_settings ALTER COLUMN updated_at SET DEFAULT now();
