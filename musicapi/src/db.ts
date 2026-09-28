import { Pool } from "pg";
import { config } from "./config.js";

export const pool = new Pool({ connectionString: config.databaseUrl });

/** A query runner bound to either the pool or an open transaction. */
export type QueryFn = <T>(text: string, params?: unknown[]) => Promise<T[]>;

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
 * Run `fn` inside a single database transaction: COMMIT on success, ROLLBACK on
 * any error. Used where a read + write must be atomic across tables (payments).
 */
export async function withTransaction<T>(fn: (tx: QueryFn) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const tx: QueryFn = async <R>(text: string, params: unknown[] = []) =>
      (await client.query(text, params)).rows as R[];
    const result = await fn(tx);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw err;
  } finally {
    client.release();
  }
}
