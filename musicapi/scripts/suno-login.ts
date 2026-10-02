/**
 * One-time interactive Suno sign-in that captures the durable `__client` cookie.
 *
 * Opens your installed Chrome, you sign in with Google normally, and this script
 * captures the Clerk `__client` refresh cookie, encrypts it, and stores it on the
 * `suno_accounts` row. After that the API's auto-refresh mints JWTs from it — no
 * further manual logins.
 *
 *   npx tsx scripts/suno-login.ts
 *   ACCOUNT_LABEL=iamduke1987@gmail.com npx tsx scripts/suno-login.ts
 *
 * Requires Google Chrome installed (uses channel "chrome"; no browser download).
 * The Google password is never seen by this script — you type it into Google's
 * own page.
 */
import "dotenv/config";
import { chromium } from "playwright-core";
import { pool } from "../src/db.js";
import { encryptCookie } from "../src/cookieCrypto.js";

const label = process.env.ACCOUNT_LABEL ?? "iamduke1987@gmail.com";
const TIMEOUT_MS = Number(process.env.LOGIN_TIMEOUT_MS ?? 10 * 60_000);

async function main(): Promise<void> {
  const browser = await chromium.launch({ headless: false, channel: "chrome" });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("https://suno.com/", { waitUntil: "domcontentloaded", timeout: 60_000 });

  console.log("\n=== Sign in to Suno with Google in the opened Chrome window ===");
  console.log("Waiting for a Clerk session (up to", Math.round(TIMEOUT_MS / 1000), "s)...\n");

  const deadline = Date.now() + TIMEOUT_MS;
  let signedIn = false;
  while (Date.now() < deadline) {
    try {
      signedIn = await page.evaluate(
        () => Boolean((window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session),
      );
    } catch {
      /* navigating */
    }
    if (signedIn) break;
    await new Promise((r) => setTimeout(r, 2000));
  }
  if (!signedIn) {
    await browser.close();
    throw new Error("Timed out waiting for a signed-in Suno session.");
  }

  const cookies = await context.cookies("https://suno.com");
  const clientCookie = cookies.find((c) => c.name === "__client")?.value;
  const ajs = cookies.find((c) => c.name === "ajs_anonymous_id")?.value;
  if (!clientCookie) {
    await browser.close();
    throw new Error("Signed in, but no __client cookie was found.");
  }

  const exists = await pool.query("SELECT id FROM suno_accounts WHERE label = $1", [label]);
  if (exists.rows.length) {
    await pool.query(
      "UPDATE suno_accounts SET type = 'paid', client_cookie = $1, device_id = COALESCE($2, device_id), is_active = true WHERE label = $3",
      [encryptCookie(clientCookie), ajs ?? null, label],
    );
  } else {
    await pool.query(
      "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, 'paid', $2, $3)",
      [label, encryptCookie(clientCookie), ajs ?? ""],
    );
  }

  const info = await pool.query(
    "SELECT label, type, is_active, length(client_cookie) AS cookie_len FROM suno_accounts WHERE label = $1",
    [label],
  );
  console.log("\n=== Stored durable Suno session ===");
  console.log(JSON.stringify(info.rows[0]));
  console.log("Auto-refresh will now mint JWTs from __client; no more manual logins.\n");

  await browser.close();
  await pool.end().catch(() => {});
}

main().catch((e) => {
  console.error("suno-login failed:", e instanceof Error ? e.message : e);
  process.exit(1);
});
