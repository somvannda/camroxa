-- Studio backend gaps: unified operations, analysis cache, clip social layer,
-- render artifacts.
--
-- Additive only. No foreign keys to tables whose ownership is still in flux:
-- clip ids may be provider clip ids, so they are stored as TEXT with indexes.
-- Enable each block as its feature is wired; the tables are inert until used.

-- ---------------------------------------------------------------------------
-- 1. Unified operation record (replaces per-verb shapes)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS studio_operations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id UUID REFERENCES studio_projects(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,                      -- stems | extend | cover | remaster | mashup |
                                           -- replace_section | add_vocals | add_instrumental |
                                           -- cover_image | upload_extend | upload_cover |
                                           -- persona | render | clip_op
  target_type TEXT NOT NULL,               -- clip | upload | project | persona
  target_id TEXT,                          -- provider or local id, TEXT on purpose
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  state TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
  progress SMALLINT CHECK (progress IS NULL OR progress BETWEEN 0 AND 100),
  error_code TEXT,
  error_message TEXT,
  result JSONB,
  credits_charged INTEGER NOT NULL DEFAULT 0 CHECK (credits_charged >= 0),
  credits_refunded INTEGER NOT NULL DEFAULT 0 CHECK (credits_refunded >= 0),
  provider_job_id TEXT,
  attempts SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS studio_operations_user_created_idx
  ON studio_operations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS studio_operations_project_created_idx
  ON studio_operations (project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS studio_operations_open_idx
  ON studio_operations (state, created_at)
  WHERE state IN ('queued','running');

-- A failed or cancelled op must never hold credits.
ALTER TABLE studio_operations
  DROP CONSTRAINT IF EXISTS studio_operations_refund_bounds;
ALTER TABLE studio_operations
  ADD CONSTRAINT studio_operations_refund_bounds
  CHECK (credits_refunded <= credits_charged);

-- ---------------------------------------------------------------------------
-- 2. Clip analysis cache (downbeats, waveform, lyrics, sections)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS studio_clip_analysis (
  clip_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('downbeats','waveform','lyrics','sections')),
  variant TEXT NOT NULL DEFAULT '',        -- e.g. lyrics variant
  source_hash TEXT NOT NULL,               -- invalidate when the source changes
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (clip_id, kind, variant, source_hash)
);

CREATE INDEX IF NOT EXISTS studio_clip_analysis_lookup_idx
  ON studio_clip_analysis (clip_id, kind, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3. Clip social layer (permissions + comments)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clip_permissions (
  clip_id TEXT PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('private','unlisted','public')),
  can_remix BOOLEAN NOT NULL DEFAULT false,
  show_remixes BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clip_permission_grants (
  clip_id TEXT NOT NULL,
  grantee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {view,comment,remix}
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (clip_id, grantee_id)
);

CREATE TABLE IF NOT EXISTS clip_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clip_id TEXT NOT NULL,
  parent_id UUID REFERENCES clip_comments(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS clip_comments_clip_idx
  ON clip_comments (clip_id, created_at DESC)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS clip_comments_author_idx
  ON clip_comments (author_id, created_at DESC);

-- Per-user thread visibility ("hide comments on my clip") without deleting data.
CREATE TABLE IF NOT EXISTS clip_comment_settings (
  clip_id TEXT PRIMARY KEY,
  comments_enabled BOOLEAN NOT NULL DEFAULT true,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 4. Render jobs + artifacts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS studio_render_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id UUID REFERENCES studio_projects(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK (scope IN ('full','range','multitrack','stems','clip')),
  state TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_code TEXT,
  error_message TEXT,
  operation_id UUID REFERENCES studio_operations(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS studio_render_jobs_project_idx
  ON studio_render_jobs (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS studio_render_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  render_job_id UUID NOT NULL REFERENCES studio_render_jobs(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('mix','stem','clip','archive','manifest')),
  label TEXT,                              -- track name for stems
  format TEXT NOT NULL,                    -- wav | mp3 | zip | json
  bytes BIGINT CHECK (bytes IS NULL OR bytes >= 0),
  duration_s NUMERIC(10,3),
  storage_key TEXT NOT NULL,
  checksum TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS studio_render_artifacts_job_idx
  ON studio_render_artifacts (render_job_id, created_at);
