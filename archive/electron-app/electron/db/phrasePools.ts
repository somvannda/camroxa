import * as pg from "pg";
import { generateAlbumCandidates, generateOpeningPairs, generateTitleCandidates } from "./poolGenerators";

function normalize(text: string) {
  return String(text || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

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

export async function poolStats(cfg: DbCfg) {
  const client = await connect(cfg);
  try {
    const openings = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from opening_pairs",
    );
    const titles = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from title_pool",
    );
    const albums = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from album_pool",
    );
    return {
      openings: openings.rows[0] as { total: number; unused: number },
      titles: titles.rows[0] as { total: number; unused: number },
      albums: albums.rows[0] as { total: number; unused: number },
    };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function importTitles(cfg: DbCfg, titles: string[]) {
  const rows = titles
    .map((t) => String(t || "").trim())
    .filter(Boolean)
    .map((t) => ({ title: t, norm: normalize(t) }))
    .filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };

  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1000;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk = rows.slice(i, i + chunkSize);
      const values: string[] = [];
      const params: string[] = [];
      let p = 1;
      for (const r of chunk) {
        values.push(`($${p++}, $${p++})`);
        params.push(r.title, r.norm);
      }
      const q = `insert into title_pool(title, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function importAlbums(cfg: DbCfg, albums: string[]) {
  const rows = albums
    .map((t) => String(t || "").trim())
    .filter(Boolean)
    .map((t) => ({ album: t, norm: normalize(t) }))
    .filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };

  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1000;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk = rows.slice(i, i + chunkSize);
      const values: string[] = [];
      const params: string[] = [];
      let p = 1;
      for (const r of chunk) {
        values.push(`($${p++}, $${p++})`);
        params.push(r.album, r.norm);
      }
      const q = `insert into album_pool(album, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function importOpenings(cfg: DbCfg, pairs: Array<{ line1: string; line2: string }>) {
  const rows = pairs
    .map((p) => ({ line1: String(p.line1 || "").trim(), line2: String(p.line2 || "").trim() }))
    .filter((x) => x.line1 && x.line2)
    .map((x) => ({ ...x, norm: normalize(`${x.line1} ${x.line2}`) }))
    .filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };

  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1000;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk = rows.slice(i, i + chunkSize);
      const values: string[] = [];
      const params: string[] = [];
      let p = 1;
      for (const r of chunk) {
        values.push(`($${p++}, $${p++}, $${p++})`);
        params.push(r.line1, r.line2, r.norm);
      }
      const q = `insert into opening_pairs(line1, line2, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end().catch(() => undefined);
  }
}

export type Picked = { opening?: { id: number; line1: string; line2: string }; title?: { id: number; title: string }; album?: { id: number; album: string } };

export async function pickAndMark(cfg: DbCfg, opts: { opening?: boolean; title?: boolean; album?: boolean }) {
  const client = await connect(cfg);
  const maxAttempts = 6;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      await client.query("begin");
      const out: Picked = {};

      async function pickOne(table: "opening_pairs" | "title_pool" | "album_pool") {
        const selectUnused = table === "opening_pairs"
          ? "select id, line1, line2 from opening_pairs where used_count = 0 order by random() limit 1 for update skip locked"
          : table === "title_pool"
            ? "select id, title from title_pool where used_count = 0 order by random() limit 1 for update skip locked"
            : "select id, album from album_pool where used_count = 0 order by random() limit 1 for update skip locked";
        const selectLeast = table === "opening_pairs"
          ? "select id, line1, line2 from opening_pairs order by used_count asc, random() limit 1 for update skip locked"
          : table === "title_pool"
            ? "select id, title from title_pool order by used_count asc, random() limit 1 for update skip locked"
            : "select id, album from album_pool order by used_count asc, random() limit 1 for update skip locked";
        let r = await client.query(selectUnused);
        if (!r.rows.length) r = await client.query(selectLeast);
        return r.rows[0] ?? null;
      }

    if (opts.opening) {
      const r = await pickOne("opening_pairs");
      if (r) {
        await client.query("update opening_pairs set used_count = used_count + 1, used_at = now() where id = $1", [r.id]);
        out.opening = { id: Number(r.id), line1: String(r.line1), line2: String(r.line2) };
      }
    }

    if (opts.title) {
      const r = await pickOne("title_pool");
      if (r) {
        await client.query("update title_pool set used_count = used_count + 1, used_at = now() where id = $1", [r.id]);
        out.title = { id: Number(r.id), title: String(r.title) };
      }
    }

    if (opts.album) {
      const r = await pickOne("album_pool");
      if (r) {
        await client.query("update album_pool set used_count = used_count + 1, used_at = now() where id = $1", [r.id]);
        out.album = { id: Number(r.id), album: String(r.album) };
      }
    }

      await client.query("commit");
      return out;
    } catch (e) {
      await client.query("rollback").catch(() => undefined);
      const code = e && typeof e === "object" ? (e as { code?: string }).code : undefined;
      const msg = e instanceof Error ? e.message : String(e);
      const isDeadlock = code === "40P01" || /deadlock detected/i.test(msg);
      if (!isDeadlock || attempt === maxAttempts - 1) throw e;
      await new Promise((r) => setTimeout(r, 50 * (attempt + 1)));
      continue;
    }
  }

  await client.end().catch(() => undefined);
  throw new Error("Failed to pick (retry exhausted)");
}

export async function pickBatchAndMark(cfg: DbCfg, opts: { opening?: boolean; title?: boolean; album?: boolean; n: number }) {
  const n = Math.max(1, Math.min(200, Math.floor(opts.n)));
  const client = await connect(cfg);
  const maxAttempts = 6;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      await client.query("begin");
      const out: {
        openings: Array<{ id: number; line1: string; line2: string }>;
        titles: Array<{ id: number; title: string }>;
        albums: Array<{ id: number; album: string }>;
      } = { openings: [], titles: [], albums: [] };

      if (opts.opening) {
        const r = await client.query(
          "select id, line1, line2 from opening_pairs order by used_count asc, random() limit $1 for update skip locked",
          [n],
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update opening_pairs set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.openings = r.rows.map((x) => ({ id: Number(x.id), line1: String(x.line1), line2: String(x.line2) }));
        }
      }

      if (opts.title) {
        const r = await client.query(
          "select id, title from title_pool order by used_count asc, random() limit $1 for update skip locked",
          [n],
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update title_pool set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.titles = r.rows.map((x) => ({ id: Number(x.id), title: String(x.title) }));
        }
      }

      if (opts.album) {
        const r = await client.query(
          "select id, album from album_pool order by used_count asc, random() limit $1 for update skip locked",
          [n],
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update album_pool set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.albums = r.rows.map((x) => ({ id: Number(x.id), album: String(x.album) }));
        }
      }

      await client.query("commit");
      return out;
    } catch (e) {
      await client.query("rollback").catch(() => undefined);
      const code = e && typeof e === "object" ? (e as { code?: string }).code : undefined;
      const msg = e instanceof Error ? e.message : String(e);
      const isDeadlock = code === "40P01" || /deadlock detected/i.test(msg);
      if (!isDeadlock || attempt === maxAttempts - 1) throw e;
      await new Promise((r) => setTimeout(r, 50 * (attempt + 1)));
      continue;
    }
  }

  await client.end().catch(() => undefined);
  throw new Error("Failed to pick batch (retry exhausted)");
}

export async function listPool(
  cfg: DbCfg,
  input: { kind: "titles" | "albums" | "openings"; limit: number; offset: number },
): Promise<
  | { kind: "titles"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
  | { kind: "albums"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
  | { kind: "openings"; rows: Array<{ id: number; line1: string; line2: string; usedCount: number; createdAt: string }> }
> {
  const limit = Math.max(1, Math.min(500, Math.floor(input.limit)));
  const offset = Math.max(0, Math.floor(input.offset));
  const client = await connect(cfg);
  try {
    if (input.kind === "titles") {
      const r = await client.query(
        "select id, title as text, used_count as \"usedCount\", created_at as \"createdAt\" from title_pool order by id desc limit $1 offset $2",
        [limit, offset],
      );
      return { kind: "titles", rows: r.rows.map((x) => ({ id: Number(x.id), text: String(x.text), usedCount: Number(x.usedCount), createdAt: String(x.createdAt) })) };
    }
    if (input.kind === "albums") {
      const r = await client.query(
        "select id, album as text, used_count as \"usedCount\", created_at as \"createdAt\" from album_pool order by id desc limit $1 offset $2",
        [limit, offset],
      );
      return { kind: "albums", rows: r.rows.map((x) => ({ id: Number(x.id), text: String(x.text), usedCount: Number(x.usedCount), createdAt: String(x.createdAt) })) };
    }
    const r = await client.query(
      "select id, line1, line2, used_count as \"usedCount\", created_at as \"createdAt\" from opening_pairs order by id desc limit $1 offset $2",
      [limit, offset],
    );
    return {
      kind: "openings",
      rows: r.rows.map((x) => ({
        id: Number(x.id),
        line1: String(x.line1),
        line2: String(x.line2),
        usedCount: Number(x.usedCount),
        createdAt: String(x.createdAt),
      })),
    };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function generateAndInsert(cfg: DbCfg, input: { kind: "titles" | "albums" | "openings"; count: number }) {
  const target = Math.max(1, Math.min(200000, Math.floor(input.count)));
  let inserted = 0;
  let rounds = 0;
  while (inserted < target && rounds < 40) {
    rounds += 1;
    const remaining = target - inserted;
    const batch = Math.min(5000, remaining);
    if (input.kind === "titles") {
      const candidates = generateTitleCandidates(batch * 2);
      const r = await importTitles(cfg, candidates);
      inserted += r.inserted;
    } else if (input.kind === "albums") {
      const candidates = generateAlbumCandidates(batch * 2);
      const r = await importAlbums(cfg, candidates);
      inserted += r.inserted;
    } else {
      const candidates = generateOpeningPairs(batch * 2);
      const r = await importOpenings(cfg, candidates);
      inserted += r.inserted;
    }
    if (rounds >= 6 && inserted === 0) break;
  }
  return { inserted };
}

export async function clearPool(cfg: DbCfg, kind: "titles" | "albums" | "openings") {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    await client.query("set local lock_timeout = '3s'");
    await client.query("set local statement_timeout = '20s'");
    if (kind === "titles") await client.query("truncate table title_pool restart identity");
    else if (kind === "albums") await client.query("truncate table album_pool restart identity");
    else await client.query("truncate table opening_pairs restart identity");
    await client.query("commit");
    return { ok: true as const };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    return { ok: false as const, message: e instanceof Error ? e.message : "Failed to clear" };
  } finally {
    await client.end().catch(() => undefined);
  }
}
