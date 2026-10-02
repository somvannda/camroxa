import "dotenv/config";
import { pool } from "../src/db.js";
import { createHash } from "node:crypto";

function hash(tok: string) {
  return createHash("sha256").update(tok).digest("hex");
}

async function main() {
  const candidates = [
    "sk-test-123",
    "sk-test-1234567890abcdef1234567890abcdef",
  ];
  for (const c of candidates) {
    const h = hash(c);
    const r = await pool.query(
      "SELECT id, key_prefix, credits, is_active FROM api_keys WHERE key_hash = $1",
      [h],
    );
    console.log(`KEY "${c}": rows=${r.rows.length}`, r.rows[0] ?? "");
  }
  // Also dump all key prefixes with credits >= 0
  const all = await pool.query(
    "SELECT key_prefix, credits, is_active FROM api_keys ORDER BY credits DESC",
  );
  console.log("\nAll keys:");
  for (const k of all.rows) {
    console.log(" ", k.key_prefix, "credits:", k.credits, k.is_active ? "" : "[inactive]");
  }
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
