import "dotenv/config";
import { pool } from "../src/db.js";
import { encryptSecret, isEncrypted } from "../src/crypto.js";

/**
 * One-off, idempotent backfill: encrypt any `suno_accounts.client_cookie`
 * values still stored in plaintext. Safe to re-run — already-encrypted rows
 * are skipped.
 */
async function main() {
  const { rows } = await pool.query<{ id: string; client_cookie: string }>(
    "SELECT id, client_cookie FROM suno_accounts",
  );
  let updated = 0;
  for (const row of rows) {
    if (!row.client_cookie || isEncrypted(row.client_cookie)) continue;
    await pool.query("UPDATE suno_accounts SET client_cookie = $1 WHERE id = $2", [
      encryptSecret(row.client_cookie),
      row.id,
    ]);
    updated++;
  }
  console.log(`Encrypted ${updated} of ${rows.length} account cookie(s).`);
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
