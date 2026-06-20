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

export type DbVideoTemplateRow = {
  id: string;
  name: string;
  source: "builtin" | "user";
  template: unknown;
  updatedAt: string;
};

export async function listVideoTemplates(cfg: DbCfg): Promise<DbVideoTemplateRow[]> {
  const client = await connect(cfg);
  try {
    const r = await client.query("select uid, name, source, template, updated_at from video_templates order by name asc");
    return r.rows.map((x) => ({
      id: String(x.uid),
      name: String(x.name ?? ""),
      source: String(x.source ?? "user") === "builtin" ? "builtin" : "user",
      template: x.template,
      updatedAt: new Date(x.updated_at).toISOString(),
    }));
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function getVideoTemplate(cfg: DbCfg, id: string): Promise<DbVideoTemplateRow | null> {
  const client = await connect(cfg);
  try {
    const r = await client.query("select uid, name, source, template, updated_at from video_templates where uid = $1", [id]);
    if (!r.rows.length) return null;
    const x = r.rows[0];
    return {
      id: String(x.uid),
      name: String(x.name ?? ""),
      source: String(x.source ?? "user") === "builtin" ? "builtin" : "user",
      template: x.template,
      updatedAt: new Date(x.updated_at).toISOString(),
    };
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function upsertVideoTemplate(cfg: DbCfg, input: { id: string; name: string; source: "builtin" | "user"; template: unknown }) {
  const client = await connect(cfg);
  try {
    await client.query(
      `insert into video_templates(uid, name, source, template, created_at, updated_at)
       values ($1,$2,$3,$4::jsonb, now(), now())
       on conflict (uid) do update set
         name = excluded.name,
         source = excluded.source,
         template = excluded.template,
         updated_at = now()`,
      [input.id, input.name, input.source, JSON.stringify(input.template)],
    );
  } finally {
    await client.end().catch(() => undefined);
  }
}

export async function deleteVideoTemplate(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from video_templates where uid = $1", [id]);
  } finally {
    await client.end().catch(() => undefined);
  }
}
