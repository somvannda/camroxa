import "dotenv/config";
import { pool as dbPool } from "../src/db.js";
import { AccountPool } from "../src/pool.js";

async function main() {
  const pool = await AccountPool.load(dbPool);
  const paid = pool.accounts.find((a) => a.label.includes("iamduke")) ?? pool.accounts[0];
  console.log("Using account", paid.label, "type", paid.type);
  const client = paid.client;
  const required = await client.captchaRequired();
  console.log("captchaRequired:", required);
  console.log("billing info:", await client.billingInfo().catch((e) => e.message));
  await dbPool.end();
}

main().catch(console.error);
