-- Studio project persistence.
--
-- The arrangement is stored as a versioned JSON document while the public API
-- exposes project CRUD. Tracks, clips, takes, automation, mixer state and
-- timeline metadata live under `data`; the schema can later be normalised
-- without changing the public project id or ownership model.

CREATE TABLE IF NOT EXISTS studio_projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'Untitled Project',
  major_version INTEGER NOT NULL DEFAULT 2,
  bpm INTEGER NOT NULL DEFAULT 120 CHECK (bpm BETWEEN 20 AND 300),
  time_signature TEXT NOT NULL DEFAULT '4/4',
  data JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS studio_projects_user_updated_idx
  ON studio_projects (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS studio_projects_user_title_idx
  ON studio_projects (user_id, lower(title));
