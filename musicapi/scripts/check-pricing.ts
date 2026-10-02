import "dotenv/config";
import { pool } from "../src/db.js";

async function main() {
  const r = await pool.query("SELECT count(*)::text AS c FROM pricing");
  console.log("pricing rows:", r.rows[0].c);
  const rows = await pool.query(
    "SELECT endpoint, credit_cost FROM pricing ORDER BY endpoint",
  );
  for (const row of rows.rows) {
    console.log(`${row.credit_cost.toString().padStart(2, " ")}  ${row.endpoint}`);
  }
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
