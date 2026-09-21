import "dotenv/config";
import { pool } from "../src/db.js";

const jwt = process.env.PAID_JWT;
if (!jwt) throw new Error("Set PAID_JWT env var.");

const label = process.env.PAID_LABEL ?? "iamduke1987@gmail.com";
const deviceId = process.env.PAID_DEVICE_ID ?? "f47ac10b-58cc-4372-a567-0e02b2c3d479";

async function main() {
  const exists = await pool.query("SELECT id FROM suno_accounts WHERE label = $1", [label]);
  if (exists.rows.length) {
    await pool.query(
      "UPDATE suno_accounts SET type='paid', client_cookie=$1, device_id=$2, is_active=true WHERE label=$3",
      [jwt, deviceId, label],
    );
    console.log("Updated existing paid account:", label);
  } else {
    await pool.query(
      "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, 'paid', $2, $3)",
      [label, jwt, deviceId],
    );
    console.log("Inserted paid account:", label);
  }
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
