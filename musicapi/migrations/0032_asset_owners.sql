-- 0032_asset_owners — explicit asset → owner mapping for authenticated media access.
--
-- Owns every id a caller may fetch through an authenticated route: clip ids and
-- upload-session ids. Previously ownership was derived by scanning
-- `jobs.result_json` / `usage_logs.result_json` with a LIKE pattern on every
-- stream/download/status request; this table is the indexed, exact source of
-- truth. The scan remains only as a fallback for legacy/unrecorded ids.
--
-- Idempotent: re-running is a no-op.

CREATE TABLE IF NOT EXISTS asset_owners (
  asset_id TEXT PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_asset_owners_user_id ON asset_owners (user_id);
