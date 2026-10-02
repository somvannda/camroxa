import "dotenv/config";
import { pool } from "../src/db.js";
import { createHash } from "node:crypto";

async function main() {
  const key = process.env.TEST_KEY || "sk-test-123";
  const hash = createHash("sha256").update(key).digest("hex");
  const res = await pool.query(
    "UPDATE api_keys SET credits = 5000 WHERE key_hash = $1 RETURNING key_prefix, credits, is_active",
    [hash],
  );
  if (res.rows.length === 0) {
    console.log(`No key found for hash ${hash.slice(0, 12)}…`);
    // try by prefix
    const byPrefix = await pool.query(
      "SELECT id, key_prefix, credits FROM api_keys WHERE key_prefix LIKE $1 LIMIT 1",
      [key.slice(0, 8) + "%"],
    );
    if (byPrefix.rows.length) {
      const id = byPrefix.rows[0].id;
      await pool.query("UPDATE api_keys SET credits = 5000 WHERE id = $1", [id]);
      console.log(`Topped up key ${byPrefix.rows[0].key_prefix} to 5000 credits.`);
    } else {
      console.log("Could not locate key by hash or prefix.");
    }
  } else {
    console.log(`Topped up ${res.rows[0].key_prefix}: credits = ${res.rows[0].credits}, active=${res.rows[0].is_active}`);
  }
  await pool.end();
}

main().catch(console.error);
