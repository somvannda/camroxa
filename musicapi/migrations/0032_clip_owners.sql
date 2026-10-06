-- 0032_clip_owners — explicit clip → owner mapping for authenticated media access.
--
-- `clipOwnedByOtherUser` previously derived ownership by scanning
-- `jobs.result_json` / `usage_logs.result_json` with a LIKE pattern on every
-- stream/download. This table is the indexed, exact source of truth; the scan
-- remains only as a fallback for legacy/unrecorded ids.
--
-- Idempotent: re-running is a no-op.

CREATE TABLE IF NOT EXISTS clip_owners (
  clip_id TEXT PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clip_owners_user_id ON clip_owners (user_id);
