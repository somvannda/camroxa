import { Pool, PoolClient } from "pg";
import { config } from "./config.js";

export const pool = new Pool({ connectionString: config.databaseUrl });

/** Run a query and return typed rows. */
export async function query<T>(text: string, params: unknown[] = []): Promise<T[]> {
  const res = await pool.query(text, params);
  return res.rows as T[];
}

/** Run a single query and return the first row (or null). */
export async function queryOne<T>(text: string, params: unknown[] = []): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows[0] ?? null;
}

/**
 * Run `fn` inside a single transaction on one pooled connection. Commits on
 * success, rolls back on any error, and always releases the connection. Use for
 * read-modify-write sequences (e.g. balance checks + decrements) that must be
 * atomic with respect to concurrent requests.
 */
export async function withTransaction<T>(fn: (client: PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (e) {
    try {
      await client.query("ROLLBACK");
    } catch {
      // A failed rollback (e.g. the connection already dropped) must not mask
      // the original error.
    }
    throw e;
  } finally {
    client.release();
  }
}
