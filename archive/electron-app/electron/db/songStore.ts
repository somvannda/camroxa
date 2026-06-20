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

export type SongRowInput = {
  songUid: string;
  title: string;
  album: string;
  lyricsRaw: string;
  lyricsPolished: string;
  songDescription: string;
  songStructure: string;
  language: string;
  creativity: number;
  batchId?: string;
  batchIndex?: number;
  status?: string;
  createdAtIso?: string;
};

export async function upsertSong(cfg: DbCfg, input: SongRowInput) {
  const client = await connect(cfg);
  try {
    await client.query(
      `insert into songs(
        song_uid, title, album,
        lyrics_raw, lyrics_polished,
        song_description, song_structure,
        language, creativity, batch_id, batch_index,
        status, created_at
      ) values (
        $1,$2,$3,
        $4,$5,
        $6,$7,
        $8,$9,$10,$11,
        $12, coalesce($13::timestamp, now())
      )
      on conflict (song_uid) do update set
        title = excluded.title,
        album = excluded.album,
        lyrics_raw = excluded.lyrics_raw,
        lyrics_polished = excluded.lyrics_polished,
        song_description = excluded.song_description,
        song_structure = excluded.song_structure,
        language = excluded.language,
        creativity = excluded.creativity,
        batch_id = excluded.batch_id,
        batch_index = excluded.batch_index,
        status = excluded.status`,
      [
        input.songUid,
        input.title,
        input.album,
        input.lyricsRaw,
        input.lyricsPolished,
        input.songDescription,
        input.songStructure,
        input.language,
        input.creativity,
        input.batchId ?? null,
        typeof input.batchIndex === "number" && Number.isFinite(input.batchIndex) ? Math.floor(input.batchIndex) : null,
        input.status ?? "generated",
        input.createdAtIso ?? null,
      ],
    );
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function insertHistory(cfg: DbCfg, input: { kind: string; message: string; songUid?: string }) {
  const client = await connect(cfg);
  try {
    await client.query("insert into history(kind, song_uid, message) values ($1, $2, $3)", [
      input.kind,
      input.songUid ?? null,
      input.message,
    ]);
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getRecentForUniqueness(cfg: DbCfg, n: number) {
  const limit = Math.max(1, Math.min(5000, Math.floor(n)));
  const client = await connect(cfg);
  try {
    const r = await client.query(
      "select title, album, lyrics_raw, lyrics_polished from songs order by created_at desc limit $1",
      [limit],
    );
    return r.rows.map((x) => ({
      title: String(x.title ?? ""),
      album: String(x.album ?? ""),
      lyricsRaw: String(x.lyrics_raw ?? ""),
      lyricsPolished: String(x.lyrics_polished ?? ""),
    }));
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function listSongsByBatchId(cfg: DbCfg, batchId: string) {
  const client = await connect(cfg);
  try {
    const res = await client.query(
      "select song_uid, title, album, lyrics_raw, lyrics_polished, song_description, song_structure, language, creativity, batch_id, batch_index, created_at from songs where batch_id = $1 order by created_at asc",
      [batchId],
    );
    return res.rows.map((r) => ({
      id: String(r.song_uid),
      title: String(r.title ?? ""),
      album: String(r.album ?? ""),
      lyricsRaw: String(r.lyrics_raw ?? ""),
      lyricsPolished: String(r.lyrics_polished ?? ""),
      songDescription: String(r.song_description ?? ""),
      songStructure: String(r.song_structure ?? ""),
      language: String(r.language ?? "English"),
      creativity: Number(r.creativity ?? 50),
      batchId: String(r.batch_id ?? ""),
      batchIndex: typeof r.batch_index === "number" ? Number(r.batch_index) : r.batch_index ? Number(r.batch_index) : undefined,
      createdAt: new Date(r.created_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function clearGenerated(cfg: DbCfg) {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    await client.query("set local lock_timeout = '3s'");
    await client.query("set local statement_timeout = '20s'");
    await client.query("truncate table history restart identity");
    await client.query("truncate table songs restart identity");
    await client.query("commit");
    return { ok: true as const };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    return { ok: false as const, message: e instanceof Error ? e.message : "Failed to clear" };
  } finally {
    await client.end().catch(() => undefined);
  }
}
