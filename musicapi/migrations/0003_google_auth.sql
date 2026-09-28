-- 0003_google_auth — password-less Google accounts.
-- (Was `scripts/migrate-google-auth.ts`.) No-op on a database created from 0001.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE;

ALTER TABLE users
  ALTER COLUMN password_hash DROP NOT NULL;
