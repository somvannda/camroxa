-- 0010_app_settings — operator-managed runtime settings, stored one JSONB
-- document per logical group (currently `brand` and `alerts`). A key/value shape
-- keeps the schema stable as new groups are added without a migration each time.
-- `updated_by` is ON DELETE SET NULL so the last editor is recorded but the row
-- survives an admin account being removed.

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by UUID REFERENCES users(id) ON DELETE SET NULL
);
