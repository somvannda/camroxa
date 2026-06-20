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

export type DbProfileRow = {
  id: string;
  name: string;
  folderName: string;
  runPrefix: string;
  logoPath: string;
  createdAt: string;
  updatedAt: string;
};

export async function listProfiles(cfg: DbCfg): Promise<DbProfileRow[]> {
  const client = await connect(cfg);
  try {
    const r = await client.query(
      "select uid, name, folder_name, run_prefix, logo_path, created_at, updated_at from profiles order by created_at asc",
    );
    return r.rows.map((x) => ({
      id: String(x.uid),
      name: String(x.name ?? ""),
      folderName: String(x.folder_name ?? ""),
      runPrefix: String(x.run_prefix ?? ""),
      logoPath: String(x.logo_path ?? ""),
      createdAt: new Date(x.created_at).toISOString(),
      updatedAt: new Date(x.updated_at).toISOString(),
    }));
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function upsertProfiles(cfg: DbCfg, items: Array<Pick<DbProfileRow, "id" | "name" | "folderName" | "runPrefix" | "logoPath">>) {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    for (const p of items) {
      await client.query(
        `insert into profiles(uid, name, folder_name, run_prefix, logo_path, created_at, updated_at)
         values ($1,$2,$3,$4,$5, now(), now())
         on conflict (uid) do update set
           name = excluded.name,
           folder_name = excluded.folder_name,
           run_prefix = excluded.run_prefix,
           logo_path = excluded.logo_path,
           updated_at = now()`,
        [p.id, p.name, p.folderName, p.runPrefix, p.logoPath],
      );
    }
    await client.query("commit");
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function syncProfiles(cfg: DbCfg, items: Array<Pick<DbProfileRow, "id" | "name" | "folderName" | "runPrefix" | "logoPath">>) {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    if (!items.length) {
      await client.query("delete from profiles");
    } else {
      await client.query("delete from profiles where uid <> all($1::text[])", [items.map((x) => x.id)]);
    }
    for (const p of items) {
      await client.query(
        `insert into profiles(uid, name, folder_name, run_prefix, logo_path, created_at, updated_at)
         values ($1,$2,$3,$4,$5, now(), now())
         on conflict (uid) do update set
           name = excluded.name,
           folder_name = excluded.folder_name,
           run_prefix = excluded.run_prefix,
           logo_path = excluded.logo_path,
           updated_at = now()`,
        [p.id, p.name, p.folderName, p.runPrefix, p.logoPath],
      );
    }
    await client.query("commit");
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end().catch(() => undefined);
  }
}
