/**
 * Read-only live probe: use the pool's stored cookie to read Suno billing info.
 * No generation, no credits spent.
 */
import { decryptCookie } from "./src/cookieCrypto.js";
import { query } from "./src/db.js";

async function main(): Promise<void> {
  const rows = (await query<{
    label: string;
    client_cookie: string;
    credits_left: number | null;
  }>(
    `select label, client_cookie, credits_left from suno_accounts
     where client_cookie is not null order by credits_left desc nulls last limit 3`
  )) as unknown as
    | Array<{ label: string; client_cookie: string; credits_left: number | null }>
    | { rows: Array<{ label: string; client_cookie: string; credits_left: number | null }> };
  const list = Array.isArray(rows) ? rows : rows.rows;
  for (const row of list) {
    try {
      const cookie = decryptCookie(row.client_cookie);
      process.env.SUNO_CLIENT_COOKIE = cookie;
      const suno = await import("./src/suno.js");
      const info = await suno.getBillingInfo();
      console.log(
        row.label,
        "OK",
        JSON.stringify({
          credits_left: (info as { credits_left?: number }).credits_left,
          plan: (info as { plan?: unknown }).plan ?? null,
        })
      );
      return;
    } catch (error) {
      console.log(row.label, "FAILED", error instanceof Error ? error.message.slice(0, 160) : error);
    }
  }
}

void main();
