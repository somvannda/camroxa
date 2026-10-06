import "dotenv/config";
import { query } from "../src/db.js";
import { extractOwnedAssetIds } from "../src/clips.js";

/**
 * Backfill `asset_owners` from existing job/usage results so legacy clips and
 * upload sessions resolve through the indexed ownership map
 * (migrations/0032_asset_owners.sql).
 *
 *   npx tsx scripts/backfill-asset-owners.ts
 *
 * Idempotent: `ON CONFLICT DO NOTHING` means an asset's first-recorded owner
 * wins, so re-running (or running after new jobs finalize) never reassigns.
 */

interface ResultRow {
  id: string;
  user_id: string;
  result_json: unknown;
}

async function backfillFrom(table: "jobs" | "usage_logs", jobIdColumn: boolean): Promise<number> {
  const rows = await query<ResultRow>(
    `SELECT id, user_id, result_json FROM ${table}
      WHERE user_id IS NOT NULL AND result_json IS NOT NULL`,
  );
  let inserted = 0;
  for (const row of rows) {
    const ids = extractOwnedAssetIds(row.result_json);
    for (const assetId of ids) {
      const written = await query<{ asset_id: string }>(
        `INSERT INTO asset_owners (asset_id, user_id, job_id)
         VALUES ($1, $2, $3)
         ON CONFLICT (asset_id) DO NOTHING
         RETURNING asset_id`,
        [assetId, row.user_id, jobIdColumn ? row.id : null],
      );
      inserted += written.length;
    }
  }
  return inserted;
}

const fromJobs = await backfillFrom("jobs", true);
const fromUsage = await backfillFrom("usage_logs", false);
console.log(
  `backfill-asset-owners: inserted ${fromJobs} owner(s) from jobs, ${fromUsage} from usage_logs`,
);
process.exit(0);
