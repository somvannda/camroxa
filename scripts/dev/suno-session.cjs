#!/usr/bin/env node
/**
 * Open the Suno reference Studio in a browser signed in as the configured account.
 *
 * The platform backend already holds durable `suno_accounts` rows; this script decrypts
 * one of those `__client` cookies with musicapi's own helpers and injects it, so no
 * password or Chrome profile is involved. Default mode opens a headed browser for manual
 * capture work; `--probe` checks the session headless and exits.
 *
 * Usage:
 *   node scripts/dev/suno-session.cjs                    # headed, opens /studio
 *   node scripts/dev/suno-session.cjs --probe            # headless session check
 *   node scripts/dev/suno-session.cjs --label acct-2     # different suno_accounts row
 *   node scripts/dev/suno-session.cjs --url https://suno.com/create
 *
 * Credentials never leave this process: the cookie is not printed or written to disk.
 */
const fs = require("node:fs");
const path = require("node:path");

const repo = path.resolve(__dirname, "..", "..");
const musicapi = path.join(repo, "musicapi");
const playwright = require(path.join(repo, "camxora.com", "node_modules", "playwright"));

function loadEnv() {
  for (const line of fs.readFileSync(path.join(musicapi, ".env"), "utf8").split(/\r?\n/)) {
    const match = line.match(/^\uFEFF?([A-Z_]+)=(.*)$/);
    if (!match) continue;
    process.env[match[1]] = match[2].replace(/^["']|["']$/g, "").trim();
  }
}

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

(async () => {
  const label = arg("label", "iamduke1987@gmail.com");
  const target = arg("url", "https://suno.com/studio");
  const probe = process.argv.includes("--probe");

  loadEnv();
  const { query, pool } = require(path.join(musicapi, "dist", "db.js"));
  const { decryptCookie } = require(path.join(musicapi, "dist", "cookieCrypto.js"));

  const rows = await query(
    "SELECT label, client_cookie FROM suno_accounts WHERE label = $1 AND is_active = true",
    [label]
  );
  await pool.end();
  if (!rows.length) throw new Error(`No active suno_accounts row for "${label}".`);
  const cookie = decryptCookie(rows[0].client_cookie);
  if (!cookie) throw new Error("Could not decrypt that account's __client cookie.");

  const browser = await playwright.chromium.launch({ headless: probe });
  const context = await browser.newContext();
  await context.addCookies([
    {
      name: "__client",
      value: cookie,
      domain: ".suno.com",
      path: "/",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
  const page = await context.newPage();
  await page.goto(target, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(5000);

  const signedOut = await page.getByRole("button", { name: /sign in|log in/i }).count();
  console.log(`url=${page.url()}`);
  console.log(`account=${rows[0].label}`);
  console.log(`signed-in=${signedOut === 0}`);

  if (probe) {
    await browser.close();
    process.exit(signedOut === 0 ? 0 : 1);
  }

  console.log("Leave this window open for capture work; close it to end the session.");
  await new Promise((resolve) => browser.on("disconnected", resolve));
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
