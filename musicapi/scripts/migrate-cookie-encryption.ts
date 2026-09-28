import "dotenv/config";
import { pool } from "../src/db.js";
import { encryptCookie, isEncryptedCookie } from "../src/cookieCrypto.js";

/**
 * One-off migration: encrypt any `suno_accounts.client_cookie` rows that were
 * written before encryption was introduced. Idempotent — already-encrypted rows
 * are skipped, so it is safe to re-run.
 */
async function main() {
  const { rows } = await pool.query<{ id: string; label: string; client_cookie: string }>(
    "SELECT id, label, client_cookie FROM suno_accounts ORDER BY created_at",
  );

  let migrated = 0;
  for (const row of rows) {
    if (isEncryptedCookie(row.client_cookie)) continue;
    await pool.query("UPDATE suno_accounts SET client_cookie = $1 WHERE id = $2", [
      encryptCookie(row.client_cookie),
      row.id,
    ]);
    migrated += 1;
  }

  console.log(`Cookie encryption migration complete: ${migrated} of ${rows.length} row(s) encrypted.`);
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
