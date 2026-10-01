-- 0016_download_purchases — charge `GET /me/download` once per clip.
--
-- A customer pays for a file, not for a transfer: the first download of a given
-- clip in a given format costs `wav_download`/`mp3_download` credits, and any
-- later download of that same clip is free. This row is the record of that
-- purchase, claimed before the charge so two concurrent first-downloads cannot
-- both pay. It is deleted again when delivery fails, so a refunded download can
-- be retried.
--
-- Deliberately not a `usage_logs` row: that table is an append-only record of
-- settled API calls, and this needs a uniqueness constraint to claim on.

CREATE TABLE IF NOT EXISTS download_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  clip_id TEXT NOT NULL,
  format TEXT NOT NULL,
  credits INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, clip_id, format)
);

CREATE INDEX IF NOT EXISTS idx_download_purchases_user ON download_purchases(user_id, created_at DESC);
