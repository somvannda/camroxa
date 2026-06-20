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

export async function getAppJson<T>(cfg: DbCfg, key: string): Promise<T | null> {
  const client = await connect(cfg);
  try {
    const r = await client.query("select value from app_json where key = $1", [key]);
    if (!r.rows.length) return null;
    return r.rows[0].value as T;
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function setAppJson(cfg: DbCfg, key: string, value: unknown) {
  const client = await connect(cfg);
  try {
    await client.query(
      `insert into app_json(key, value, updated_at) values ($1, $2::jsonb, now())
       on conflict (key) do update set value = excluded.value, updated_at = now()`,
      [key, JSON.stringify(value)],
    );
  } finally {
    await client.end().catch(() => undefined);
  }
}

