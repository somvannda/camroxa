import "dotenv/config";
import { existsSync } from "node:fs";
import { AccountPool } from "./pool.js";
import { buildServer } from "./server.js";
import { recoverInterruptedJobs, refundJobCredits } from "./jobs.js";
import { pool as dbPool } from "./db.js";

const port = Number(process.env.PORT ?? 4003);

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
  // A fresh deployment has an empty database and no accounts.json (it is not
  // shipped), so only fall back when the file is actually present.
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

// Jobs left non-terminal by a previous process can never be resumed, so mark
// them failed on boot rather than reporting them as perpetually running.
try {
  const recovered = await recoverInterruptedJobs();
  if (recovered.length > 0) {
    console.warn(`Marked ${recovered.length} interrupted job(s) as failed.`);
  }
  for (const job of recovered) {
    try {
      const refunded = await refundJobCredits(job, "Job interrupted by server restart");
      if (refunded > 0) {
        console.warn(`Refunded ${refunded} credit(s) for interrupted job ${job.id}.`);
      }
    } catch (e) {
      console.error(`Failed to refund interrupted job ${job.id}:`, e);
    }
  }
} catch (e) {
  console.error("Failed to recover interrupted jobs:", e);
}

// --- graceful shutdown ----------------------------------------------------
// On SIGTERM/SIGINT: stop accepting connections, let Fastify drain in-flight
// requests, then wait (bounded) for detached background workers to persist
// their terminal state before closing the DB pool and exiting. Jobs that are
// still running when the drain times out are refunded on the next boot by
// recoverInterruptedJobs()/refundJobCredits().
let shuttingDown = false;
async function shutdown(signal: string, code = 0): Promise<void> {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`Received ${signal}; shutting down gracefully...`);
  try {
    await app.close();
  } catch (e) {
    console.error("Error while closing the HTTP server:", e);
  }
  try {
    await dbPool.end();
  } catch (e) {
    console.error("Error while closing the database pool:", e);
  }
  console.log("Shutdown complete.");
  process.exit(code);
}

process.on("SIGTERM", () => void shutdown("SIGTERM"));
process.on("SIGINT", () => void shutdown("SIGINT"));
// Detached workers are designed never to reject (see runDetached in server.ts);
// log any stray rejection instead of letting Node crash the process.
process.on("unhandledRejection", (reason) => {
  console.error("Unhandled promise rejection:", reason);
});
// An uncaught exception leaves the process in an unknown state, so log it and
// shut down cleanly rather than continuing to serve with corrupted state.
process.on("uncaughtException", (err) => {
  console.error("Uncaught exception:", err);
  void shutdown("uncaughtException", 1);
});

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
