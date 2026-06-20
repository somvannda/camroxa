import * as pg from "pg";

export async function testPostgresConnection(opts: {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
  timeoutMs?: number;
}) {
  const client = new pg.Client({
    host: opts.host,
    port: opts.port,
    user: opts.user,
    password: opts.password,
    database: opts.database,
  });

  const timeoutMs = opts.timeoutMs ?? 5000;
  const timeout = setTimeout(() => {
    void client.end();
  }, timeoutMs);

  try {
    await client.connect();
    const res = await client.query("select 1 as ok");
    const ok = res?.rows?.[0]?.ok === 1;
    return { ok, message: ok ? "Connection OK" : "Connected but test query failed" };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : "Connection failed" };
  } finally {
    clearTimeout(timeout);
    await client.end().catch(() => undefined);
  }
}
