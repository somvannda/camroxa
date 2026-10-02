import "dotenv/config";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pool } from "../src/db.js";
import { hashPassword } from "../src/appAuth.js";

function hashKey(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

async function ensureUser(email: string, password: string, role: "user" | "admin", name: string): Promise<string> {
  const existing = await pool.query("SELECT id FROM users WHERE email = $1", [email]);
  if (existing.rows.length) return existing.rows[0].id as string;
  const hash = await hashPassword(password);
  const res = await pool.query(
    "INSERT INTO users (email, password_hash, role, name) VALUES ($1, $2, $3, $4) RETURNING id",
    [email, hash, role, name],
  );
  return res.rows[0].id as string;
}

async function main() {
  const adminId = await ensureUser("admin@example.com", "admin123", "admin", "Admin");
  const userId = await ensureUser("user@example.com", "user123", "user", "Test User");
  void adminId;

  // Migrate api-keys.json -> api_keys (for the test user)
  try {
    const keys = JSON.parse(readFileSync("api-keys.json", "utf8")) as { key: string; name: string; credits: number }[];
    for (const k of keys) {
      const exists = await pool.query("SELECT 1 FROM api_keys WHERE key_hash = $1", [hashKey(k.key)]);
      if (exists.rows.length) continue;
      await pool.query(
        "INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, $2, $3, $4, $5)",
        [userId, k.name, hashKey(k.key), k.key.slice(0, 8), k.credits],
      );
    }
  } catch {
    // no api-keys.json — skip
  }

  // Migrate accounts.json -> suno_accounts
  try {
    const accounts = JSON.parse(readFileSync("accounts.json", "utf8")) as { id: string; clientCookie: string; deviceId: string }[];
    for (const a of accounts) {
      const exists = await pool.query("SELECT 1 FROM suno_accounts WHERE label = $1", [a.id]);
      if (exists.rows.length) continue;
      await pool.query(
        "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, 'free', $2, $3)",
        [a.id, a.clientCookie, a.deviceId],
      );
    }
  } catch {
    // no accounts.json — skip
  }

  // Seed pricing
  const pricing: Array<[string, string | null, number]> = [
    ["music", null, 9],
    ["lyrics", null, 2],
    ["extend", null, 9],
    ["cover", null, 9],
    ["sounds", null, 9],
    ["stems", null, 9],
    ["remaster", null, 9],
    ["mashup", null, 9],
    ["add_vocals", null, 9],
    ["add_instrumental", null, 9],
    ["replace_section", null, 9],
    ["cover_image", null, 5],
    ["persona", null, 9],
    ["wav", null, 1],
    ["upload_extend", null, 9],
    ["upload_cover", null, 9],
    ["upload_init", null, 1],
    ["upload_register", null, 1],
    ["recovery_audio", null, 9],
    ["mp4_generate", null, 5],
    ["boost_style", null, 9],
    ["midi_generate", null, 9],
    ["voice_phrase", null, 9],
    ["voice_validate", null, 1],
    ["voice_record", null, 1],
    ["voice_generate", null, 9],
    ["voice_apply", null, 9],
    ["voice_extend", null, 9],
    ["lyrics_detail", null, 1],
    ["wav_detail", null, 1],
    ["stems_detail", null, 1],
    ["video_detail", null, 1],
    ["cover_detail", null, 1],
    ["subtitle_detail", null, 1],
    ["recovery_detail", null, 1],
    ["mp4_detail", null, 1],
    ["midi_detail", null, 1],
    ["timestamped_lyrics_detail", null, 1],
  ];
  for (const [endpoint, model, cost] of pricing) {
    const exists = await pool.query("SELECT 1 FROM pricing WHERE endpoint = $1", [endpoint]);
    if (exists.rows.length) continue;
    await pool.query("INSERT INTO pricing (endpoint, model, credit_cost) VALUES ($1, $2, $3)", [endpoint, model, cost]);
  }

  // Seed credit packs
  const packs = await pool.query("SELECT 1 FROM credit_packs LIMIT 1");
  if (!packs.rows.length) {
    await pool.query(
      `INSERT INTO credit_packs (amount, price, currency) VALUES
         (1000, 20500, 'KHR'),
         (5000, 102500, 'KHR'),
         (20000, 410000, 'KHR'),
         (100000, 2000000, 'KHR'),
         (500000, 9500000, 'KHR'),
         (1000, 5, 'USD'),
         (5000, 25, 'USD'),
         (20000, 100, 'USD'),
         (100000, 488, 'USD'),
         (500000, 2317, 'USD')`,
    );
  }

  console.log("Seed complete.");
  console.log("  Admin: admin@example.com / admin123");
  console.log("  User:  user@example.com / user123");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
