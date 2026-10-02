/**
 * Capture the durable Suno `__client` cookie for the auto-refresh mechanism.
 *
 * Two modes:
 *
 * 1. Reuse your existing Chrome profile (default, no sign-in needed).
 *    If `suno.com` is already signed in in Chrome, this reads `__client` from the
 *    profile and stores it. Chrome must be fully closed first (the profile is
 *    locked while it runs).
 *
 *      npm run suno:login
 *      # profile overrides:
 *      SUNO_CHROME_PROFILE="C:\Users\me\AppData\Local\Google\Chrome\User Data" \
 *      SUNO_CHROME_PROFILE_DIR="Default" npm run suno:login
 *
 * 2. Fresh interactive sign-in (for email/password accounts):
 *
 *      SUNO_LOGIN_FRESH=1 npm run suno:login
 *
 *    Note: a fresh automation context cannot complete a Google sign-in — Google
 *    blocks automated browsers — so mode 1 is required for Google accounts.
 *
 * Either way, after this the API mints JWTs from `__client` automatically.
 */
import "dotenv/config";
import os from "node:os";
import path from "node:path";
import fs, { existsSync } from "node:fs";
import { chromium, type BrowserContext } from "playwright-core";
import { pool } from "../src/db.js";
import { encryptCookie } from "../src/cookieCrypto.js";

const label = process.env.ACCOUNT_LABEL ?? "iamduke1987@gmail.com";
const TIMEOUT_MS = Number(process.env.LOGIN_TIMEOUT_MS ?? 5 * 60_000);

function defaultProfileDir(): string {
  if (process.platform === "win32") {
    return path.join(os.homedir(), "AppData", "Local", "Google", "Chrome", "User Data");
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "Google", "Chrome");
  }
  return path.join(os.homedir(), ".config", "google-chrome");
}

async function store(clientCookie: string, ajs: string | undefined): Promise<void> {
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
}

async function cookieFrom(context: BrowserContext): Promise<{ client: string; ajs?: string } | null> {
  const cookies = await context.cookies("https://suno.com");
  const client = cookies.find((c) => c.name === "__client")?.value;
  if (!client) return null;
  const ajs = cookies.find((c) => c.name === "ajs_anonymous_id")?.value;
  return { client, ajs };
}

async function main(): Promise<void> {
  const fresh = process.env.SUNO_LOGIN_FRESH === "1";
  const profileDir = process.env.SUNO_CHROME_PROFILE ?? defaultProfileDir();
  const profileName = process.env.SUNO_CHROME_PROFILE_DIR ?? "Default";

  let context: BrowserContext;
  let browser = null as Awaited<ReturnType<typeof chromium.launch>> | null;

  if (!fresh && existsSync(profileDir)) {
    console.log(`Reusing Chrome profile: ${profileDir} (${profileName})`);
    try {
      context = await chromium.launchPersistentContext(profileDir, {
        channel: "chrome",
        headless: false,
        args: [`--profile-directory=${profileName}`],
      });
    } catch (e) {
      throw new Error(
        `Could not open the Chrome profile (${e instanceof Error ? e.message : e}). ` +
          `Fully quit Chrome (all windows, and check the tray) and retry.`,
      );
    }
  } else {
    browser = await chromium.launch({ channel: "chrome", headless: false });
    context = await browser.newContext();
    console.log("Opened a fresh browser — sign in to Suno in the window (email/password only).");
  }

  const page = context.pages()[0] ?? (await context.newPage());
  await page.goto("https://suno.com/", { waitUntil: "domcontentloaded", timeout: 60_000 }).catch(() => {});

  // Look for an existing session first (profile mode usually has one).
  let found = await cookieFrom(context);
  if (found) {
    const signedIn = await page
      .evaluate(() => Boolean((window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session))
      .catch(() => false);
    if (!signedIn) found = null; // __client exists but this is a signed-out/anonymous session
  }

  const deadline = Date.now() + TIMEOUT_MS;
  while (!found && Date.now() < deadline) {
    console.log("Waiting for a signed-in Suno session...");
    await new Promise((r) => setTimeout(r, 3000));
    const signedIn = await page
      .evaluate(() => Boolean((window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session))
      .catch(() => false);
    if (signedIn) found = await cookieFrom(context);
  }

  if (!found) {
    await context.close().catch(() => {});
    await browser?.close().catch(() => {});
    throw new Error(
      "No signed-in Suno session found. If you reused a profile, make sure you are signed into suno.com in Chrome and Chrome is fully closed.",
    );
  }

  await store(found.client, found.ajs);
  await context.close().catch(() => {});
  await browser?.close().catch(() => {});
  await pool.end().catch(() => {});
}

main().catch((e) => {
  console.error("suno-login failed:", e instanceof Error ? e.message : e);
  process.exit(1);
});
