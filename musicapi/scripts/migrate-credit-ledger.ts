import "dotenv/config";
import { pool } from "../src/db.js";

// Ties credit-ledger rows to the job that caused them. `type` is already
// constrained to ('purchase','adjust','spend','refund'); the partial unique index
// on (job_id, type) makes per-job spend/refund writes idempotent (ON CONFLICT),
// so a retried/duplicated finalize can never refund twice.
const SCHEMA_SQL = `
ALTER TABLE credit_transactions
  ADD COLUMN IF NOT EXISTS job_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_tx_job_type
  ON credit_transactions (job_id, type)
  WHERE job_id IS NOT NULL;
`;

async function main() {
  await pool.query(SCHEMA_SQL);
  console.log("[migrate] credit_transactions.job_id + uq_credit_tx_job_type ensured.");
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
