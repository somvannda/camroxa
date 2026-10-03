import "dotenv/config";
import { existsSync } from "node:fs";
import { AccountPool } from "./pool.js";
import { buildServer } from "./server.js";
import { pool as dbPool, query, queryOne } from "./db.js";
import { encryptCookie } from "./cookieCrypto.js";
import { config } from "./config.js";
import { loadRuntimeSettings } from "./runtimeSettings.js";

const port = Number(process.env.PORT ?? 4003);

// Load admin-managed integration settings (env is the fallback) before the
// account pool, so a DB-configured Suno cookie/device is available to seed.
await loadRuntimeSettings();

let pool: AccountPool;
try {
  pool = await AccountPool.fromDb();
} catch (e) {
  // Most commonly a COOKIE_ENCRYPTION_KEY that doesn't match the stored rows;
  // decryptCookie() says so. Surface it as a clear boot failure, not a raw
  // top-level-await rejection.
  console.error(`Failed to load Suno accounts from the database: ${e instanceof Error ? e.message : e}`);
  console.error(
    "Check COOKIE_ENCRYPTION_KEY (must match the key the rows were encrypted with) and DATABASE_URL.",
  );
  process.exit(1);
}
if (pool.size === 0) {
  // Production provisioning: a fresh host can seed its first account purely from
  // a deploy secret, so no one has to sign in on the server. Prefer the durable
  // `__client` cookie; a 'JWT' also works but expires in ~1h and cannot refresh.
  const envSecret = (config.clientCookie || config.jwt || "").trim();
  if (envSecret) {
    try {
      const label = process.env.SUNO_ACCOUNT_LABEL ?? "env-seed";
      const existing = await queryOne<{ id: string }>(
        "SELECT id FROM suno_accounts WHERE label = $1",
        [label],
      );
      if (existing) {
        await query(
          "UPDATE suno_accounts SET type = 'paid', client_cookie = $1, device_id = COALESCE($2, device_id), is_active = true WHERE label = $3",
          [encryptCookie(envSecret), config.deviceId || null, label],
        );
      } else {
        await query(
          "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, 'paid', $2, $3)",
          [label, encryptCookie(envSecret), config.deviceId || ""],
        );
      }
      pool = await AccountPool.fromDb();
      console.log(`[seed] Seeded Suno account '${label}' from env (SUNO_CLIENT_COOKIE/SUNO_JWT).`);
    } catch (e) {
      console.error("[seed] env seeding failed:", e instanceof Error ? e.message : e);
    }
  }
}
if (pool.size === 0) {
  const accountsFile = process.env.ACCOUNTS_FILE ?? "accounts.json";
  if (existsSync(accountsFile)) {
    console.warn("No active Suno accounts in the database; falling back to accounts.json");
    pool = AccountPool.fromJsonFile(accountsFile);
  } else {
    console.warn(
      `No active Suno accounts in the database and no ${accountsFile}; starting with an empty pool. ` +
        "Generation requests will fail until a Suno account is added.",
    );
  }
}

const app = await buildServer({ pool });

let shuttingDown = false;
async function shutdown(signal: string, exitCode = 0): Promise<void> {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`${signal} received — draining in-flight jobs and shutting down...`);
  // Safety net: if draining hangs, don't wait forever (container stop grace).
  const timer = setTimeout(() => {
    console.error("[shutdown] drain timed out; forcing exit.");
    process.exit(1);
  }, 35_000);
  timer.unref();
  try {
    // Runs the `onClose` hook, which awaits in-flight job workers.
    await app.close();
  } catch (e) {
    console.error("[shutdown] error closing server:", e);
  }
  try {
    await dbPool.end();
  } catch (e) {
    console.error("[shutdown] error closing db pool:", e);
  }
  console.log("[shutdown] done.");
  process.exit(exitCode);
}

// Detached job workers are `.catch()`-guarded, but anything that still escapes
// (or an uncaught throw) must not kill the process silently.
process.on("unhandledRejection", (reason) => {
  console.error(
    "[fatal] unhandled rejection:",
    reason instanceof Error ? reason.stack ?? reason.message : reason,
  );
});
process.on("uncaughtException", (err) => {
  console.error("[fatal] uncaught exception:", err.stack ?? err.message);
  void shutdown("uncaughtException", 1);
});

process.on("SIGTERM", () => void shutdown("SIGTERM"));
process.on("SIGINT", () => void shutdown("SIGINT"));

app
  .listen({ port, host: "0.0.0.0" })
  .then((addr) => {
    console.log(`Suno API listening on ${addr}`);
    console.log(`accounts=${pool.size}`);
  })
  .catch((e) => {
    console.error("Failed to start server:", e);
    process.exit(1);
  });
