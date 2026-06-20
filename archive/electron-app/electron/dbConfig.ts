import path from "node:path";
import { promises as fs } from "node:fs";

export type DbConnectionConfig = {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
};

export function getDbConfigPath(opts: { isPackaged: boolean; appPath: string; execPath: string }) {
  const baseDir = opts.isPackaged ? path.dirname(opts.execPath) : opts.appPath;
  return path.join(baseDir, "db-connection.json");
}

export async function readDbConfig(filePath: string): Promise<DbConnectionConfig | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw) as Partial<DbConnectionConfig>;
    const host = String(parsed.host ?? "").trim();
    const user = String(parsed.user ?? "").trim();
    const database = String(parsed.database ?? "").trim();
    const port = Number(parsed.port ?? 0);
    const password = String(parsed.password ?? "");
    if (!host || !user || !database || !Number.isFinite(port) || port <= 0) return null;
    return { host, port, user, password, database };
  } catch {
    return null;
  }
}

export async function writeDbConfig(filePath: string, cfg: DbConnectionConfig) {
  const out: DbConnectionConfig = {
    host: String(cfg.host || "").trim(),
    port: Math.max(1, Math.floor(Number(cfg.port) || 5432)),
    user: String(cfg.user || "").trim(),
    password: String(cfg.password || ""),
    database: String(cfg.database || "").trim(),
  };
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(out, null, 2), "utf-8");
}

