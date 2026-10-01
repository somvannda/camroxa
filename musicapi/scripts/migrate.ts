import "dotenv/config";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { pool } from "../src/db.js";

// Resolve `migrations/` relative to this file, not the caller's CWD.
const MIGRATIONS_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "migrations");

// Arbitrary but stable key for a session-level lock, so two runners can never
// apply the same migration concurrently.
const ADVISORY_LOCK_KEY = 4_172_001;

/**
 * Apply every `migrations/*.sql` file in filename order, exactly once.
 *
 * Applied versions are recorded in `schema_migrations`, so re-running is a
 * no-op. Each file is applied inside a transaction together with its
 * bookkeeping row: a failure rolls the whole file back, leaving the database
 * untouched. All migration SQL is written idempotently (`IF NOT EXISTS`, guarded
 * updates), so a database that predates this runner can be adopted safely.
 */
async function main() {
  const client = await pool.connect();
  let locked = false;
  try {
    await client.query("SELECT pg_advisory_lock($1)", [ADVISORY_LOCK_KEY]);
    locked = true;

    await client.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `);

    const files = readdirSync(MIGRATIONS_DIR)
      .filter((f) => f.endsWith(".sql"))
      .sort();

    const { rows } = await client.query<{ version: string }>("SELECT version FROM schema_migrations");
    const applied = new Set(rows.map((r) => r.version));

    let ran = 0;
    for (const file of files) {
      if (applied.has(file)) continue;
      const sql = readFileSync(join(MIGRATIONS_DIR, file), "utf8");
      await client.query("BEGIN");
      try {
        await client.query(sql);
        await client.query("INSERT INTO schema_migrations (version) VALUES ($1)", [file]);
        await client.query("COMMIT");
      } catch (err) {
        await client.query("ROLLBACK");
        throw new Error(`migration ${file} failed: ${(err as Error).message}`);
      }
      console.log(`[migrate] applied ${file}`);
      ran += 1;
    }

    console.log(`[migrate] done: ${ran} applied, ${files.length - ran} already up to date.`);
  } finally {
    if (locked) {
      await client.query("SELECT pg_advisory_unlock($1)", [ADVISORY_LOCK_KEY]).catch(() => undefined);
    }
    client.release();
    await pool.end();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
