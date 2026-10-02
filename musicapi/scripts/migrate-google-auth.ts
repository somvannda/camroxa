import "dotenv/config";
import { pool } from "../src/db.js";

async function main() {
  // google_id column + password_hash nullable (allows password-less Google users)
  await pool.query(`
    ALTER TABLE users
      ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE,
      ALTER COLUMN password_hash DROP NOT NULL
  `);
  const rows = await pool.query(
    "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'users' AND column_name IN ('google_id','password_hash') ORDER BY column_name",
  );
  for (const r of rows.rows) {
    console.log(`${r.column_name}\ttype=${r.data_type}\tnullable=${r.is_nullable}`);
  }
  await pool.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
