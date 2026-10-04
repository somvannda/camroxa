/**
 * Capture the durable Suno `__client` cookie for the auto-refresh mechanism.
 *
 * Chrome refuses DevTools (CDP) on the *default* user-data-dir, so we stage a
 * copy of the target profile into a temp dir and launch from there. The copied
 * cookies decrypt on the same Windows user (DPAPI), so an existing suno.com
 * session carries over — no sign-in needed.
 *
 *   SUNO_CHROME_PROFILE_DIR="Profile 1" npm run suno:login
 *
 * Options:
 *   SUNO_CHROME_PROFILE      full path to Chrome "User Data" (default: standard)
 *   SUNO_CHROME_PROFILE_DIR  profile folder name (default: "Default")
 *   SUNO_LOGIN_FRESH=1       skip staging; open a fresh browser (email/password only)
 *   ACCOUNT_LABEL            suno_accounts.label to upsert (default iamduke1987@gmail.com)
 *   LOGIN_TIMEOUT_MS         wait for a Clerk session (default 5 min)
 */
import "dotenv/config";
import os from "node:os";
import { existsSync, cpSync, mkdtempSync, rmSync } from "node:fs";
import path from "node:path";
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

const SKIP_DIRS = new Set([
  "Cache", "Code Cache", "GPUCache", "ShaderCache", "Media Cache", "DawnCache",
  "GrShaderCache", "Service Worker", "Crashpad", "BrowserMetrics",
]);

/** Copy the profile into a temp user-data-dir Chrome will allow CDP on. */
function stageProfile(userDataDir: string, profileName: string): string {
  const tmp = mkdtempSync(path.join(os.tmpdir(), "camxora-chrome-"));
  const localState = path.join(userDataDir, "Local State");
  if (existsSync(localState)) cpSync(localState, path.join(tmp, "Local State"));
  const srcProfile = path.join(userDataDir, profileName);
  if (!existsSync(srcProfile)) throw new Error(`Chrome profile not found: ${srcProfile}`);
  cpSync(srcProfile, path.join(tmp, profileName), {
    recursive: true,
    filter: (src) => !SKIP_DIRS.has(path.basename(src)),
  });
  for (const f of ["SingletonLock", "SingletonCookie", "SingletonSocket"]) {
    rmSync(path.join(tmp, f), { force: true });
  }
  return tmp;
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
  // `__client` lives on auth.suno.com (Clerk), not .suno.com, so read all cookies.
  const all = await context.cookies();
  const onSuno = (c: { domain: string }) => /(^|\.)suno\.com$/.test(c.domain.replace(/^\./, ""));
  const client = all.find((c) => c.name === "__client" && onSuno(c))?.value;
  if (!client) return null;
  // Signed in iff a `__session` JWT exists and isn't expired. (suno.com does not
  // expose window.Clerk, so we cannot rely on that.)
  const session = all.find((c) => c.name === "__session" && onSuno(c))?.value;
  let signedIn = false;
  if (session) {
    try {
      const payload = JSON.parse(Buffer.from(session.split(".")[1], "base64url").toString("utf8")) as { exp?: number };
      signedIn = !payload.exp || payload.exp * 1000 > Date.now();
    } catch {
      signedIn = false;
    }
  }
  if (!signedIn) return null;
  const ajs = all.find((c) => c.name === "ajs_anonymous_id")?.value;
  return { client, ajs };
}

async function main(): Promise<void> {
  const fresh = process.env.SUNO_LOGIN_FRESH === "1";
  const srcProfileDir = process.env.SUNO_CHROME_PROFILE ?? defaultProfileDir();
  const profileName = process.env.SUNO_CHROME_PROFILE_DIR ?? "Default";
  let tempDir: string | null = null;
  let context: BrowserContext;
  let browser = null as Awaited<ReturnType<typeof chromium.launch>> | null;

  try {
    if (!fresh && existsSync(srcProfileDir)) {
      tempDir = stageProfile(srcProfileDir, profileName);
      console.log(`Staged Chrome profile -> ${tempDir} (${profileName})`);
      context = await chromium.launchPersistentContext(tempDir, {
        channel: "chrome",
        headless: false,
        args: [`--profile-directory=${profileName}`],
      });
    } else {
      browser = await chromium.launch({ channel: "chrome", headless: false });
      context = await browser.newContext();
      console.log("Opened a fresh browser — sign in to Suno (email/password only).");
    }

    const page = context.pages()[0] ?? (await context.newPage());
    await page.goto("https://suno.com/", { waitUntil: "domcontentloaded", timeout: 60_000 }).catch(() => {});

    let found = await cookieFrom(context);
    const deadline = Date.now() + TIMEOUT_MS;
    while (!found && Date.now() < deadline) {
      console.log("Waiting for a signed-in Suno session...");
      await new Promise((r) => setTimeout(r, 3000));
      found = await cookieFrom(context);
    }
    if (!found) {
      throw new Error("No signed-in Suno session found in this profile.");
    }
    await store(found.client, found.ajs);
    await context.close().catch(() => {});
  } finally {
    await browser?.close().catch(() => {});
    if (tempDir) {
      try { rmSync(tempDir, { recursive: true, force: true }); } catch { /* Chrome may still hold it */ }
    }
    await pool.end().catch(() => {});
  }
}

main().catch((e) => {
  console.error("suno-login failed:", e instanceof Error ? e.message : e);
  process.exit(1);
});
