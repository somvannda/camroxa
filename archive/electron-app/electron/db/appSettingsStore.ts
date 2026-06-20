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

export async function upsertAppSetting(cfg: DbCfg, key: string, value: string) {
  const client = await connect(cfg);
  try {
    await client.query(
      "insert into app_settings(key, value, updated_at) values ($1,$2, now()) on conflict (key) do update set value = excluded.value, updated_at = now()",
      [key, value],
    );
    return { ok: true as const };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function upsertAppSettings(cfg: DbCfg, items: Array<{ key: string; value: string }>) {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    for (const it of items) {
      await client.query(
        "insert into app_settings(key, value, updated_at) values ($1,$2, now()) on conflict (key) do update set value = excluded.value, updated_at = now()",
        [it.key, it.value],
      );
    }
    await client.query("commit");
    return { ok: true as const };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    return { ok: false as const, message: e instanceof Error ? e.message : "upsert failed" };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getAppSettings(cfg: DbCfg, keys: string[]) {
  const client = await connect(cfg);
  try {
    const res = await client.query("select key, value from app_settings where key = any($1)", [keys]);
    const out: Record<string, string> = {};
    for (const row of res.rows) {
      const k = String(row.key);
      out[k] = String(row.value ?? "");
    }
    return out;
  } finally {
    await client.end().catch(() => undefined);
  }
}
