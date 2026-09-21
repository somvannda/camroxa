import "dotenv/config";
import { AccountPool } from "./pool.js";
import { buildServer } from "./server.js";

const port = Number(process.env.PORT ?? 4003);

let pool = await AccountPool.fromDb();
if (pool.size === 0) {
  console.warn("No active Suno accounts in the database; falling back to accounts.json");
  pool = AccountPool.fromJsonFile(process.env.ACCOUNTS_FILE ?? "accounts.json");
}

const app = buildServer({ pool });

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
