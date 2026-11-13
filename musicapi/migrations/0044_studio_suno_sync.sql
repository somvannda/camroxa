-- Suno Studio project mirror (Phase 1).
--
-- Every Camxora project mirrors at most one Suno Studio project, and that Suno
-- project belongs to exactly one pinned Suno account: Suno projects are
-- account-scoped, so moving one between accounts would break access for the
-- user. `suno_state` keeps the last document we read from Suno so a later save
-- can patch the fields we understand and leave everything else untouched
-- (Suno's `state` schema is not published and is still being captured).
--
-- The project rows live in the platform database, so ids here are plain UUIDs
-- without cross-database foreign keys. The outbox stores the document snapshot
-- it still has to push: local edits coalesce onto one row, so a burst of
-- debounced saves results in a single push of the newest document.

CREATE TABLE IF NOT EXISTS studio_suno_accounts (
  user_id UUID PRIMARY KEY,
  account_label TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE studio_suno_accounts IS
  'Pinned Suno account per Camxora user; a project must always be read and written through the account that created it.';

CREATE TABLE IF NOT EXISTS studio_suno_projects (
  local_project_id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  account_label TEXT NOT NULL,
  suno_project_id TEXT NOT NULL,
  suno_version_id TEXT,
  suno_title TEXT,
  suno_state JSONB,
  state_hash TEXT,
  skipped_clip_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  archived BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'linked', 'synced', 'conflict', 'error')),
  last_error TEXT,
  last_checked_at TIMESTAMPTZ,
  synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (account_label, suno_project_id)
);

COMMENT ON COLUMN studio_suno_projects.suno_state IS
  'Last Suno document read for this project; the baseline for a merge so unknown keys survive.';
COMMENT ON COLUMN studio_suno_projects.state_hash IS
  'sha256 of the local document that produced suno_state, used to skip no-op pushes.';
COMMENT ON COLUMN studio_suno_projects.status IS
  'pending: never pushed. linked: Suno project exists, only project metadata is mirrored. synced: arrangement mirrored. conflict: Suno moved ahead. error: terminal until retried.';

CREATE INDEX IF NOT EXISTS studio_suno_projects_user_idx
  ON studio_suno_projects (user_id);

CREATE TABLE IF NOT EXISTS studio_suno_outbox (
  local_project_id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  document JSONB NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS studio_suno_outbox_due_idx
  ON studio_suno_outbox (next_attempt_at);
