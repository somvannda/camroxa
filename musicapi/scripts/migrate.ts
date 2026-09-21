import { readFileSync } from "node:fs";
import { pool } from "../src/db.js";

async function main() {
  const sql = readFileSync("scripts/schema.sql", "utf8");
  await pool.query(sql);
  console.log("Schema applied successfully.");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
