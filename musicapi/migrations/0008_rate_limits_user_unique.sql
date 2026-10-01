-- 0008_rate_limits_user_unique — one rate-limit row per user.
--
-- `rate_limits` (user_id, requests_per_minute, requests_per_day) shipped in
-- 0001 but was never wired up. Per-user limits are now read on the API-key hot
-- path and edited by admins, and the admin upsert relies on a unique key on
-- `user_id` (ON CONFLICT). Postgres does not auto-index FK columns, so the
-- unique index also serves the per-request lookup.

-- Collapse any (previously unreachable) duplicate rows, keeping the lowest id.
DELETE FROM rate_limits a
  USING rate_limits b
  WHERE a.user_id = b.user_id AND a.id > b.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_rate_limits_user ON rate_limits (user_id);
