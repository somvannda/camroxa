import "dotenv/config";
import { pool } from "../src/db.js";

async function main() {
  // First login user@example.com -> get JWT, create API key with credits
  const userRes = await pool.query(
    "SELECT id, email FROM users WHERE email = $1",
    ["user@example.com"],
  );
  const userId = userRes.rows[0].id as string;
  console.log("user id", userId);

  // Check any existing key with credits for this user
  const keys = await pool.query(
    "SELECT key_hash, key_prefix, credits FROM api_keys WHERE user_id = $1",
    [userId],
  );
  console.log("existing keys:", keys.rows.length);
  for (const k of keys.rows) {
    console.log(" ", k.key_prefix, "credits:", k.credits);
  }

  // Update first key to have >= 100 credits if none have it
  if (keys.rows.length) {
    await pool.query("UPDATE api_keys SET credits = 500 WHERE id = (SELECT id FROM api_keys WHERE user_id = $1 LIMIT 1)", [userId]);
    console.log("Credits topped up to 500 for first API key of test user.");
  } else {
    console.log("No keys yet — skip. Use user portal to create one.");
  }
  await pool.end();
}

main().catch(console.error);
