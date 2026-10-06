import "dotenv/config";
import { query } from "../src/db.js";
import { extractClipIds } from "../src/clips.js";

/**
 * Backfill `clip_owners` from existing job/usage results so legacy clips resolve
 * through the indexed ownership map (migrations/0032_clip_owners.sql).
 *
 *   npx tsx scripts/backfill-clip-owners.ts
 *
 * Idempotent: `ON CONFLICT DO NOTHING` means a clip's first-recorded owner wins,
 * so re-running (or running after new jobs finalize) never reassigns ownership.
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
    const ids = extractClipIds(row.result_json);
    for (const clipId of ids) {
      const written = await query<{ clip_id: string }>(
        `INSERT INTO clip_owners (clip_id, user_id, job_id)
         VALUES ($1, $2, $3)
         ON CONFLICT (clip_id) DO NOTHING
         RETURNING clip_id`,
        [clipId, row.user_id, jobIdColumn ? row.id : null],
      );
      inserted += written.length;
    }
  }
  return inserted;
}

const fromJobs = await backfillFrom("jobs", true);
const fromUsage = await backfillFrom("usage_logs", false);
console.log(
  `backfill-clip-owners: inserted ${fromJobs} owner(s) from jobs, ${fromUsage} from usage_logs`,
);
process.exit(0);
