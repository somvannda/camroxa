import { DatabaseSync } from "node:sqlite";

export interface TemplateRecord {
  id: string;
  name: string;
  kind: string;
  schemaVersion: number;
  path: string;
  thumbnailPath: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface ProjectRecord {
  id: string;
  name: string;
  path: string;
  thumbnailPath: string | null;
  updatedAt: number;
}

export interface PipelineJobRecord {
  id: string;
  batchId: string;
  status: string;
  stage: string;
  progress: number;
  payload: string;
  error: string | null;
  createdAt: number;
  updatedAt: number;
}

const MIGRATIONS: Array<{ version: number; sql: string }> = [
  {
    version: 1,
    sql: `
      CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        schema_version INTEGER NOT NULL DEFAULT 2,
        path TEXT NOT NULL,
        thumbnail_path TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        thumbnail_path TEXT,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS pipeline_jobs (
        id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        status TEXT NOT NULL,
        stage TEXT NOT NULL,
        progress REAL NOT NULL DEFAULT 0,
        payload TEXT NOT NULL,
        error TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_batch ON pipeline_jobs(batch_id);
      CREATE INDEX IF NOT EXISTS idx_templates_kind ON templates(kind);
    `,
  },
];

export class Store {
  constructor(private readonly db: DatabaseSync) {}

  migrate(): void {
    this.db.exec("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)");
    for (const migration of MIGRATIONS) {
      const row = this.db
        .prepare("SELECT version FROM schema_migrations WHERE version = ?")
        .get(migration.version);
      if (row) continue;
      this.db.exec("BEGIN");
      try {
        this.db.exec(migration.sql);
        this.db
          .prepare("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)")
          .run(migration.version, Date.now());
        this.db.exec("COMMIT");
      } catch (error) {
        this.db.exec("ROLLBACK");
        throw error;
      }
    }
  }

  close(): void {
    this.db.close();
  }

  getMeta(key: string): string | null {
    const row = this.db.prepare("SELECT value FROM meta WHERE key = ?").get(key) as
      | { value: string }
      | undefined;
    return row?.value ?? null;
  }

  setMeta(key: string, value: string): void {
    this.db
      .prepare("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value")
      .run(key, value);
  }

  listTemplates(kind?: string): TemplateRecord[] {
    const rows = kind
      ? this.db.prepare("SELECT * FROM templates WHERE kind = ? ORDER BY name").all(kind)
      : this.db.prepare("SELECT * FROM templates ORDER BY name").all();
    return (rows as Array<Record<string, unknown>>).map((row) => ({
      id: String(row.id),
      name: String(row.name),
      kind: String(row.kind),
      schemaVersion: Number(row.schema_version),
      path: String(row.path),
      thumbnailPath: row.thumbnail_path ? String(row.thumbnail_path) : null,
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
    }));
  }

  upsertTemplate(record: TemplateRecord): void {
    this.db
      .prepare(
        `INSERT INTO templates (id, name, kind, schema_version, path, thumbnail_path, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           name = excluded.name,
           kind = excluded.kind,
           schema_version = excluded.schema_version,
           path = excluded.path,
           thumbnail_path = excluded.thumbnail_path,
           updated_at = excluded.updated_at`,
      )
      .run(
        record.id,
        record.name,
        record.kind,
        record.schemaVersion,
        record.path,
        record.thumbnailPath,
        record.createdAt,
        record.updatedAt,
      );
  }

  deleteTemplate(id: string): void {
    this.db.prepare("DELETE FROM templates WHERE id = ?").run(id);
  }

  listProjects(): ProjectRecord[] {
    const rows = this.db.prepare("SELECT * FROM projects ORDER BY updated_at DESC").all();
    return (rows as Array<Record<string, unknown>>).map((row) => ({
      id: String(row.id),
      name: String(row.name),
      path: String(row.path),
      thumbnailPath: row.thumbnail_path ? String(row.thumbnail_path) : null,
      updatedAt: Number(row.updated_at),
    }));
  }

  upsertProject(record: ProjectRecord): void {
    this.db
      .prepare(
        `INSERT INTO projects (id, name, path, thumbnail_path, updated_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           name = excluded.name,
           path = excluded.path,
           thumbnail_path = excluded.thumbnail_path,
           updated_at = excluded.updated_at`,
      )
      .run(record.id, record.name, record.path, record.thumbnailPath, record.updatedAt);
  }

  createJob(record: PipelineJobRecord): void {
    this.db
      .prepare(
        `INSERT INTO pipeline_jobs (id, batch_id, status, stage, progress, payload, error, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        record.id,
        record.batchId,
        record.status,
        record.stage,
        record.progress,
        record.payload,
        record.error,
        record.createdAt,
        record.updatedAt,
      );
  }

  updateJob(
    id: string,
    patch: Partial<Pick<PipelineJobRecord, "status" | "stage" | "progress" | "error">>,
  ): void {
    const current = this.db
      .prepare("SELECT status, stage, progress, error FROM pipeline_jobs WHERE id = ?")
      .get(id) as
      | { status: string; stage: string; progress: number; error: string | null }
      | undefined;
    if (!current) return;
    this.db
      .prepare(
        "UPDATE pipeline_jobs SET status = ?, stage = ?, progress = ?, error = ?, updated_at = ? WHERE id = ?",
      )
      .run(
        patch.status ?? current.status,
        patch.stage ?? current.stage,
        patch.progress ?? current.progress,
        patch.error === undefined ? current.error : patch.error,
        Date.now(),
        id,
      );
  }

  listJobs(): PipelineJobRecord[] {
    const rows = this.db.prepare("SELECT * FROM pipeline_jobs ORDER BY created_at DESC").all();
    return (rows as Array<Record<string, unknown>>).map((row) => ({
      id: String(row.id),
      batchId: String(row.batch_id),
      status: String(row.status),
      stage: String(row.stage),
      progress: Number(row.progress),
      payload: String(row.payload),
      error: row.error ? String(row.error) : null,
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
    }));
  }
}

export function createDatabase(filePath: string): Store {
  const db = new DatabaseSync(filePath);
  db.exec("PRAGMA foreign_keys = ON");
  if (filePath !== ":memory:") db.exec("PRAGMA journal_mode = WAL");
  const store = new Store(db);
  store.migrate();
  return store;
}
