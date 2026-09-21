import { readFileSync } from "node:fs";
import { pool } from "../src/db.js";

async function main() {
  const sql = readFileSync("scripts/add-safe-spend-tiers.sql", "utf8");
  await pool.query(sql);
  console.log("Migration applied: safe_spend_hourly, safe_spend_daily, safe_spend_total columns added.");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
