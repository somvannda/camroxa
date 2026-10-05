-- 0030_admin_2fa — per-admin TOTP two-factor authentication.
--
-- `totp_secret` holds the RFC 4648 base32 secret, AES-256-GCM encrypted at rest
-- with the same master key as the Suno cookies (`COOKIE_ENCRYPTION_KEY`); it is
-- NULL until an admin starts enrollment. `totp_enabled` only flips to true after
-- a code verifies, so an unfinished enrollment can never lock an admin out.
--
-- Idempotent (IF NOT EXISTS / constant default), safe to adopt.

ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT false;
