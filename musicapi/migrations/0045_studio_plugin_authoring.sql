-- Designed plugins authored by Suno's agent (2026-11-13 decision).
--
-- The agent job is asynchronous and spends credits, so the job id is persisted
-- here instead of only in the editor: a reload can resume polling, and a poll
-- that lands twice can only create one library plugin. `status = 'saving'` is
-- the claim a poll takes before calling Suno, so concurrent polls cannot both
-- create the plugin.
--
-- The Suno plugin/version ids are copied onto the local document
-- (`customPlugins[].sunoPluginId` / `sunoPluginVersionId`) so the chain entry can
-- mirror them; this table is the idempotency ledger, not the source of truth.

CREATE TABLE IF NOT EXISTS studio_plugin_authoring_jobs (
  job_id TEXT PRIMARY KEY,
  local_project_id UUID NOT NULL,
  user_id UUID NOT NULL,
  instruction TEXT NOT NULL,
  required_controls JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'saving', 'ready', 'error')),
  phase TEXT,
  progress JSONB,
  display_name TEXT,
  suno_plugin_id TEXT,
  suno_plugin_version_id TEXT,
  descriptor JSONB,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE studio_plugin_authoring_jobs IS
  'Idempotency ledger for plugin authoring jobs; a completed job records the Suno plugin/version it created.';

CREATE INDEX IF NOT EXISTS studio_plugin_authoring_project_idx
  ON studio_plugin_authoring_jobs (local_project_id, created_at DESC);
