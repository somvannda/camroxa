-- Track which Suno account produced each owned asset.
--
-- jobs.account_id already records the account used for a completed job. The
-- asset map previously omitted it, so derivative operations (stems, extend,
-- cover, add vocals, replace section) could not be pinned to the account that
-- owns the source clip.

ALTER TABLE asset_owners
  ADD COLUMN IF NOT EXISTS account_id TEXT;

CREATE INDEX IF NOT EXISTS asset_owners_account_idx
  ON asset_owners (account_id);
