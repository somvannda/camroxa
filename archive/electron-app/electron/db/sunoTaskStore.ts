import * as pg from "pg";

export type DbCfg = { host: string; port: number; user: string; password: string; database: string };

async function connect(cfg: DbCfg) {
  const client = new pg.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database,
  });
  await client.connect();
  return client;
}

export type SunoTaskRow = {
  requestHash: string;
  songUid: string;
  batchId: string;
  trackNo: number | null;
  model: string;
  title: string;
  style: string;
  instrumental: boolean;
  taskId: string;
  status: string;
  audioUrlOk: string | null;
  audioUrlAlt: string | null;
  outputDirOk: string | null;
  outputDirAlt: string | null;
};

export type SunoTaskPending = {
  requestHash: string;
  songUid: string;
  batchId: string;
  trackNo: number | null;
  model: string;
  title: string;
  style: string;
  instrumental: boolean;
  taskId: string;
  status: string;
  audioUrlOk: string | null;
  audioUrlAlt: string | null;
  outputDirOk: string | null;
  outputDirAlt: string | null;
};

export async function getSunoTaskByRequestHash(cfg: DbCfg, requestHash: string): Promise<SunoTaskRow | null> {
  const client = await connect(cfg);
  try {
    const res = await client.query(
      "select request_hash, song_uid, batch_id, track_no, model, title, style, instrumental, task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir from suno_tasks where request_hash = $1",
      [requestHash],
    );
    const row = res.rows[0];
    if (!row) return null;
    return {
      requestHash: String(row.request_hash),
      songUid: String(row.song_uid || ""),
      batchId: String(row.batch_id || ""),
      trackNo: row.track_no === null || row.track_no === undefined ? null : Number(row.track_no),
      model: String(row.model || ""),
      title: String(row.title || ""),
      style: String(row.style || ""),
      instrumental: Boolean(row.instrumental),
      taskId: String(row.task_id || ""),
      status: String(row.status || ""),
      audioUrlOk: row.audio_url_ok ? String(row.audio_url_ok) : null,
      audioUrlAlt: row.audio_url_alt ? String(row.audio_url_alt) : null,
      outputDirOk: row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null,
      outputDirAlt: row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null,
    };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getLatestSunoOutputDirsBySongUid(cfg: DbCfg, songUid: string) {
  const client = await connect(cfg);
  try {
    const res = await client.query(
      "select output_dir_ok, output_dir_alt, output_dir from suno_tasks where song_uid = $1 order by updated_at desc, id desc limit 1",
      [songUid],
    );
    const row = res.rows[0];
    if (!row) return { okDir: null as string | null, altDir: null as string | null };
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getLatestSunoOutputDirsByBatchId(cfg: DbCfg, batchId: string) {
  const key = String(batchId || "").trim();
  if (!key) return { ok: false as const, message: "Batch ID is empty" };
  const client = await connect(cfg);
  try {
    const res = await client.query(
      "select output_dir_ok, output_dir_alt, output_dir from suno_tasks where batch_id = $1 order by updated_at desc, id desc limit 1",
      [key],
    );
    const row = res.rows[0];
    if (!row) return { ok: false as const, message: "No Suno output directories found for batch" };
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { ok: true as const, okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getLatestSunoBatchWithOutputDirs(cfg: DbCfg) {
  const client = await connect(cfg);
  try {
    const res = await client.query(
      "select batch_id, output_dir_ok, output_dir_alt, output_dir from suno_tasks where coalesce(output_dir_ok, output_dir) is not null order by updated_at desc, id desc limit 1",
    );
    const row = res.rows[0];
    if (!row) return { ok: false as const, message: "No batches found" };
    const batchId = String(row.batch_id || "").trim();
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { ok: true as const, batchId, okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function upsertSunoTask(
  cfg: DbCfg,
  input: {
    requestHash: string;
    songUid: string;
    batchId: string;
    trackNo?: number | null;
    model: string;
    title: string;
    style: string;
    instrumental: boolean;
    taskId: string;
    status: string;
    audioUrlOk?: string | null;
    audioUrlAlt?: string | null;
    outputDirOk?: string | null;
    outputDirAlt?: string | null;
    outputDir?: string | null;
  },
) {
  const client = await connect(cfg);
  try {
    await client.query(
      `insert into suno_tasks(
        request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
        task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir, updated_at
      ) values (
        $1,$2,$3,$4,$5,$6,$7,$8,
        $9,$10,$11,$12,$13,$14,$15, now()
      )
      on conflict (request_hash) do update set
        song_uid = excluded.song_uid,
        batch_id = excluded.batch_id,
        track_no = coalesce(excluded.track_no, suno_tasks.track_no),
        model = excluded.model,
        title = excluded.title,
        style = excluded.style,
        instrumental = excluded.instrumental,
        task_id = excluded.task_id,
        status = excluded.status,
        audio_url_ok = coalesce(excluded.audio_url_ok, suno_tasks.audio_url_ok),
        audio_url_alt = coalesce(excluded.audio_url_alt, suno_tasks.audio_url_alt),
        output_dir_ok = coalesce(excluded.output_dir_ok, suno_tasks.output_dir_ok),
        output_dir_alt = coalesce(excluded.output_dir_alt, suno_tasks.output_dir_alt),
        output_dir = coalesce(excluded.output_dir, suno_tasks.output_dir),
        updated_at = now()`,
      [
        input.requestHash,
        input.songUid,
        input.batchId,
        typeof input.trackNo === "number" && Number.isFinite(input.trackNo) ? Math.floor(input.trackNo) : null,
        input.model,
        input.title,
        input.style,
        input.instrumental,
        input.taskId,
        input.status,
        input.audioUrlOk ?? null,
        input.audioUrlAlt ?? null,
        input.outputDirOk ?? null,
        input.outputDirAlt ?? null,
        input.outputDir ?? null,
      ],
    );
    return { ok: true as const };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function listPendingSunoTasks(cfg: DbCfg, limit: number): Promise<SunoTaskPending[]> {
  const client = await connect(cfg);
  try {
    const res = await client.query(
      `select request_hash, song_uid, batch_id, track_no, model, title, style, instrumental, task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir
       from suno_tasks
       where task_id is not null
         and task_id <> ''
         and (audio_url_ok is null or audio_url_alt is null)
         and coalesce(status, '') not in ('CREATE_TASK_FAILED','GENERATE_AUDIO_FAILED')
       order by updated_at desc, id desc
       limit $1`,
      [Math.max(1, Math.min(200, limit))],
    );
    return res.rows.map((row) => ({
      requestHash: String(row.request_hash),
      songUid: String(row.song_uid || ""),
      batchId: String(row.batch_id || ""),
      trackNo: row.track_no === null || row.track_no === undefined ? null : Number(row.track_no),
      model: String(row.model || ""),
      title: String(row.title || ""),
      style: String(row.style || ""),
      instrumental: Boolean(row.instrumental),
      taskId: String(row.task_id || ""),
      status: String(row.status || ""),
      audioUrlOk: row.audio_url_ok ? String(row.audio_url_ok) : null,
      audioUrlAlt: row.audio_url_alt ? String(row.audio_url_alt) : null,
      outputDirOk: row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null,
      outputDirAlt: row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null,
    }));
  } finally {
    await client.end().catch(() => undefined);
  }
}
