-- 0025_rate_limits_window — per-window request budget and a concurrent-job cap.
--
-- `requests_per_window` mirrors sunoapi.org's documented 20 requests / 10 seconds
-- account limit; the window length is `RATE_LIMIT_USER_WINDOW_MS` (default 10s),
-- kept separate from the global edge limiter's `windowMs`.
--
-- `max_concurrent_jobs` caps how many Suno-backed jobs one user may run at once,
-- so a single user cannot occupy a small account pool. The pool's global ceiling
-- is derived from the account count at runtime (src/server.ts).
--
-- Both are nullable: NULL falls back to the configured defaults.

ALTER TABLE rate_limits ADD COLUMN IF NOT EXISTS requests_per_window INTEGER;
ALTER TABLE rate_limits ADD COLUMN IF NOT EXISTS max_concurrent_jobs INTEGER;
