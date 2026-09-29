import "dotenv/config";
import { existsSync } from "node:fs";
import { AccountPool } from "./pool.js";
import { buildServer } from "./server.js";
import { pool as dbPool } from "./db.js";

const port = Number(process.env.PORT ?? 4003);

let pool = await AccountPool.fromDb();
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
