import "dotenv/config";
import { pool } from "../src/db.js";

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','streaming','complete','error')),
  account_id TEXT,
  result_json JSONB,
  error TEXT,
  callback_url TEXT,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
  endpoint TEXT,
  model TEXT,
  prompt TEXT,
  credits INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
`;

async function main() {
  await pool.query(SCHEMA_SQL);
  console.log("[migrate] jobs table ensured.");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
