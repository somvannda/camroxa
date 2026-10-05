-- 0031_session_revocation — per-user JWT version for "log out everywhere".
--
-- The session JWT carries a `tv` claim; `requireAdmin` compares it with this
-- column. Bumping the value (see POST /admin/sessions/revoke) invalidates every
-- token minted with the previous value, so a stolen or stale 7-day token stops
-- working immediately.
--
-- Idempotent and safe to adopt (existing tokens without the claim count as 0,
-- which matches the default).

ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0;
