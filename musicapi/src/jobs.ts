import { query, queryOne } from "./db.js";

export interface Job {
  id: string;
  type:
    | "lyrics"
    | "music"
    | "extend"
    | "cover"
    | "stems"
    | "sounds"
    | "remaster"
    | "mashup"
    | "add_vocals"
    | "add_instrumental"
    | "replace_section"
    | "cover_image"
    | "persona"
    | "wav"
    | "upload_extend"
    | "upload_cover"
    | "upload_init"
    | "upload_register"
    | "recovery_audio"
    | "mp4_generate"
    | "boost_style"
    | "midi_generate"
    | "voice_phrase"
    | "voice_validate"
    | "voice_record"
    | "voice_generate"
    | "voice_apply"
    | "voice_extend"
    | "lyrics_detail"
    | "wav_detail"
    | "stems_detail"
    | "video_detail"
    | "cover_detail"
    | "subtitle_detail"
    | "recovery_detail"
    | "mp4_detail"
    | "midi_detail"
    | "timestamped_lyrics_detail";
  status: "pending" | "running" | "streaming" | "complete" | "error";
  accountId?: string;
  result?: unknown;
  error?: string;
  callbackUrl?: string;
  userId?: string;
  apiKeyId?: string;
  endpoint?: string;
  model?: string;
  prompt?: string;
  credits?: number;
  createdAt: number;
  /** Wall-clock ms when the job reached a terminal state; used for cache eviction (not persisted). */
  finishedAt?: number;
}

interface JobRow {
  id: string;
  type: string;
  status: string;
  account_id: string | null;
  user_id: string | null;
  api_key_id: string | null;
  endpoint: string | null;
  model: string | null;
  prompt: string | null;
  credits: number;
  callback_url: string | null;
  result_json: unknown;
  error: string | null;
  created_at: Date;
}

function rowToJob(row: JobRow): Job {
  return {
    id: row.id,
    type: row.type as Job["type"],
    status: row.status as Job["status"],
    accountId: row.account_id ?? undefined,
    userId: row.user_id ?? undefined,
    apiKeyId: row.api_key_id ?? undefined,
    endpoint: row.endpoint ?? undefined,
    model: row.model ?? undefined,
    prompt: row.prompt ?? undefined,
    credits: row.credits,
    callbackUrl: row.callback_url ?? undefined,
    result: row.result_json ?? undefined,
    error: row.error ?? undefined,
    createdAt: row.created_at.getTime(),
  };
}

const COLUMNS = `id, type, status, account_id, user_id, api_key_id, endpoint, model, prompt, credits, callback_url, result_json, error, created_at`;

/** Insert or update a job row. Persistence failures must never break job execution. */
export async function saveJob(job: Job): Promise<void> {
  await query(
    `INSERT INTO jobs (id, type, status, account_id, user_id, api_key_id, endpoint, model, prompt, credits, callback_url, result_json, error, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, to_timestamp($14::bigint / 1000.0), now())
     ON CONFLICT (id) DO UPDATE SET
       status = EXCLUDED.status,
       account_id = EXCLUDED.account_id,
       result_json = EXCLUDED.result_json,
       error = EXCLUDED.error,
       updated_at = now()`,
    [
      job.id,
      job.type,
      job.status,
      job.accountId ?? null,
      job.userId ?? null,
      job.apiKeyId ?? null,
      job.endpoint ?? null,
      job.model ?? null,
      job.prompt ?? null,
      job.credits ?? 0,
      job.callbackUrl ?? null,
      job.result != null ? JSON.stringify(job.result) : null,
      job.error ?? null,
      job.createdAt,
    ],
  );
}

/** Load a single job by id (used as a fallback once the in-memory map no longer holds it). */
export async function loadJob(id: string): Promise<Job | null> {
  const row = await queryOne<JobRow>(`SELECT ${COLUMNS} FROM jobs WHERE id = $1 LIMIT 1`, [id]);
  return row ? rowToJob(row) : null;
}

/**
 * Return the credits charged for a job to its API key and record the refund in
 * the credit ledger. No-op when the job was free or carries no billing owner.
 * Returns the refunded amount.
 */
export async function refundJobCredits(job: Job, reason: string): Promise<number> {
  const amount = job.credits ?? 0;
  if (!job.userId || !job.apiKeyId || amount <= 0) return 0;
  await query(
    "UPDATE api_keys SET credits = credits + $1 WHERE id = $2 AND user_id = $3",
    [amount, job.apiKeyId, job.userId],
  );
  await query(
    "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'refund', $3)",
    [job.userId, amount, `${reason} (job ${job.id})`],
  );
  return amount;
}

/**
 * Mark jobs left non-terminal by a previous process as failed so they are never
 * reported as perpetually "running". Returns the affected jobs so callers can
 * reconcile side effects (e.g. credit refunds).
 */
export async function recoverInterruptedJobs(): Promise<Job[]> {
  const rows = await query<JobRow>(
    `UPDATE jobs
        SET status = 'error',
            error = COALESCE(error, 'Interrupted by server restart'),
            updated_at = now()
      WHERE status IN ('pending', 'running', 'streaming')
      RETURNING ${COLUMNS}`,
  );
  return rows.map(rowToJob);
}
