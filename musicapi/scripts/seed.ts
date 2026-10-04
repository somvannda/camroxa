import "dotenv/config";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pool } from "../src/db.js";
import { hashPassword } from "../src/appAuth.js";
import { encryptCookie } from "../src/cookieCrypto.js";

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
        [a.id, encryptCookie(a.clientCookie), a.deviceId],
      );
    }
  } catch {
    // no accounts.json — skip
  }

  // Seed pricing
  const pricing: Array<[string, string | null, number]> = [
    ["music", null, 10],
    ["lyrics", null, 0],
    ["extend", null, 10],
    ["cover", null, 10],
    ["sounds", null, 3],
    ["stems", null, 8],
    ["stems_split", null, 20],
    ["stems_advanced", null, 12],
    ["remaster", null, 10],
    ["mashup", null, 10],
    ["add_vocals", null, 10],
    ["add_instrumental", null, 10],
    ["replace_section", null, 9],
    ["cover_image", null, 0],
    ["persona", null, 0],
    ["wav", null, 0],
    ["mp3_download", null, 0],
    ["wav_download", null, 0],
    ["upload_extend", null, 10],
    ["upload_cover", null, 10],
    ["upload_init", null, 1],
    ["upload_register", null, 1],
    ["recovery_audio", null, 10],
    ["mp4_generate", null, 2],
    ["boost_style", null, 0],
    ["midi_generate", null, 3],
    ["voice_phrase", null, 1],
    ["voice_validate", null, 1],
    ["voice_record", null, 1],
    ["voice_generate", null, 10],
    ["voice_apply", null, 10],
    ["voice_extend", null, 10],
    ["lyrics_detail", null, 0],
    ["wav_detail", null, 0],
    ["stems_detail", null, 0],
    ["video_detail", null, 0],
    ["cover_detail", null, 0],
    ["subtitle_detail", null, 0],
    ["recovery_detail", null, 0],
    ["mp4_detail", null, 0],
    ["midi_detail", null, 0],
    ["timestamped_lyrics_detail", null, 0],
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
         (1000, 5, 'USD'),
         (2300, 10, 'USD'),
         (5500, 20, 'USD'),
         (8800, 30, 'USD')`,
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
