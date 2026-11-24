import { DatabaseSync } from "node:sqlite";

export interface TemplateRecord {
  id: string;
  name: string;
  kind: string;
  schemaVersion: number;
  path: string;
  thumbnailPath: string | null;
  marketplaceItemId?: string | null;
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
  /** Absolute path of the validated render, written when the row is done. */
  outputPath?: string | null;
  /** When the render itself started (not the queue time). */
  startedAt?: number | null;
  /** Wall time the render took, written on done/failed. */
  elapsedMs?: number | null;
  /** Probed length of the rendered video, written on done. */
  durationSec?: number | null;
  /** Frames the exporter produced, written on done. */
  frames?: number | null;
  createdAt: number;
  updatedAt: number;
}

export interface PipelineBatchRecord {
  batchId: string;
  outputDir: string;
  merge: boolean;
  /** File stem for the merged output, sanitised when the batch was created. */
  mergeName: string | null;
  mergedOutput: string | null;
  status: string;
  error: string | null;
  createdAt: number;
  updatedAt: number;
}

const MIGRATIONS: Array<{ version: number; sql?: string; run?: (db: DatabaseSync) => void }> = [
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
  {
    version: 2,
    sql: `
      ALTER TABLE templates ADD COLUMN marketplace_item_id TEXT;

      CREATE UNIQUE INDEX IF NOT EXISTS idx_templates_marketplace_item
        ON templates(marketplace_item_id)
        WHERE marketplace_item_id IS NOT NULL;
    `,
  },
  {
    version: 3,
    run: (db) => {
      // A v1 database may predate the pipeline table entirely (the schema is
      // created idempotently here) and SQLite has no `ADD COLUMN IF NOT EXISTS`.
      db.exec(`
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
      `);
      const columns = db.prepare("PRAGMA table_info(pipeline_jobs)").all() as Array<{
        name: string;
      }>;
      if (!columns.some((column) => column.name === "output_path")) {
        db.exec("ALTER TABLE pipeline_jobs ADD COLUMN output_path TEXT");
      }
      db.exec(`
        CREATE TABLE IF NOT EXISTS pipeline_batches (
          batch_id TEXT PRIMARY KEY,
          output_dir TEXT NOT NULL,
          merge INTEGER NOT NULL DEFAULT 0,
          merged_output TEXT,
          status TEXT NOT NULL,
          error TEXT,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        );
      `);
    },
  },
  {
    version: 4,
    run: (db) => {
      const columns = db.prepare("PRAGMA table_info(pipeline_batches)").all() as Array<{
        name: string;
      }>;
      if (!columns.some((column) => column.name === "merge_name")) {
        db.exec("ALTER TABLE pipeline_batches ADD COLUMN merge_name TEXT");
      }
    },
  },
  {
    version: 5,
    run: (db) => {
      // Render timing and length per video: shown in the Progress rows/detail.
      const columns = db.prepare("PRAGMA table_info(pipeline_jobs)").all() as Array<{
        name: string;
      }>;
      const add = (name: string, type: string) => {
        if (!columns.some((column) => column.name === name)) {
          db.exec(`ALTER TABLE pipeline_jobs ADD COLUMN ${name} ${type}`);
        }
      };
      add("started_at", "INTEGER");
      add("elapsed_ms", "INTEGER");
      add("duration_sec", "REAL");
      add("frames", "INTEGER");
    },
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
        if (migration.run) migration.run(this.db);
        else if (migration.sql) this.db.exec(migration.sql);
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
      marketplaceItemId: row.marketplace_item_id ? String(row.marketplace_item_id) : null,
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
    }));
  }

  findTemplateByMarketplaceItem(itemId: string): TemplateRecord | null {
    const row = this.db
      .prepare("SELECT * FROM templates WHERE marketplace_item_id = ?")
      .get(itemId) as Record<string, unknown> | undefined;
    if (!row) return null;
    return {
      id: String(row.id),
      name: String(row.name),
      kind: String(row.kind),
      schemaVersion: Number(row.schema_version),
      path: String(row.path),
      thumbnailPath: row.thumbnail_path ? String(row.thumbnail_path) : null,
      marketplaceItemId: row.marketplace_item_id ? String(row.marketplace_item_id) : null,
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
    };
  }

  upsertTemplate(record: TemplateRecord): void {
    this.db
      .prepare(
        `INSERT INTO templates (id, name, kind, schema_version, path, thumbnail_path, marketplace_item_id, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           name = excluded.name,
           kind = excluded.kind,
           schema_version = excluded.schema_version,
           path = excluded.path,
           thumbnail_path = excluded.thumbnail_path,
           marketplace_item_id = excluded.marketplace_item_id,
           updated_at = excluded.updated_at`,
      )
      .run(
        record.id,
        record.name,
        record.kind,
        record.schemaVersion,
        record.path,
        record.thumbnailPath,
        record.marketplaceItemId ?? null,
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
        `INSERT INTO pipeline_jobs (id, batch_id, status, stage, progress, payload, error, output_path, started_at, elapsed_ms, duration_sec, frames, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        record.id,
        record.batchId,
        record.status,
        record.stage,
        record.progress,
        record.payload,
        record.error,
        record.outputPath ?? null,
        record.startedAt ?? null,
        record.elapsedMs ?? null,
        record.durationSec ?? null,
        record.frames ?? null,
        record.createdAt,
        record.updatedAt,
      );
  }

  updateJob(
    id: string,
    patch: Partial<
      Pick<
        PipelineJobRecord,
        | "status"
        | "stage"
        | "progress"
        | "error"
        | "outputPath"
        | "startedAt"
        | "elapsedMs"
        | "durationSec"
        | "frames"
      >
    >,
  ): void {
    const current = this.db
      .prepare(
        "SELECT status, stage, progress, error, output_path, started_at, elapsed_ms, duration_sec, frames FROM pipeline_jobs WHERE id = ?",
      )
      .get(id) as
      | {
          status: string;
          stage: string;
          progress: number;
          error: string | null;
          output_path: string | null;
          started_at: number | null;
          elapsed_ms: number | null;
          duration_sec: number | null;
          frames: number | null;
        }
      | undefined;
    if (!current) return;
    this.db
      .prepare(
        "UPDATE pipeline_jobs SET status = ?, stage = ?, progress = ?, error = ?, output_path = ?, started_at = ?, elapsed_ms = ?, duration_sec = ?, frames = ?, updated_at = ? WHERE id = ?",
      )
      .run(
        patch.status ?? current.status,
        patch.stage ?? current.stage,
        patch.progress ?? current.progress,
        patch.error === undefined ? current.error : patch.error,
        patch.outputPath === undefined ? current.output_path : patch.outputPath,
        patch.startedAt === undefined ? current.started_at : patch.startedAt,
        patch.elapsedMs === undefined ? current.elapsed_ms : patch.elapsedMs,
        patch.durationSec === undefined ? current.duration_sec : patch.durationSec,
        patch.frames === undefined ? current.frames : patch.frames,
        Date.now(),
        id,
      );
  }

  deleteJob(id: string): void {
    this.db.prepare("DELETE FROM pipeline_jobs WHERE id = ?").run(id);
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
      outputPath: row.output_path ? String(row.output_path) : null,
      startedAt: row.started_at == null ? null : Number(row.started_at),
      elapsedMs: row.elapsed_ms == null ? null : Number(row.elapsed_ms),
      durationSec: row.duration_sec == null ? null : Number(row.duration_sec),
      frames: row.frames == null ? null : Number(row.frames),
      createdAt: Number(row.created_at),
      updatedAt: Number(row.updated_at),
    }));
  }

  upsertBatch(record: PipelineBatchRecord): void {
    this.db
      .prepare(
        `INSERT INTO pipeline_batches (batch_id, output_dir, merge, merge_name, merged_output, status, error, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(batch_id) DO UPDATE SET
           output_dir = excluded.output_dir,
           merge = excluded.merge,
           merge_name = excluded.merge_name,
           merged_output = excluded.merged_output,
           status = excluded.status,
           error = excluded.error,
           updated_at = excluded.updated_at`,
      )
      .run(
        record.batchId,
        record.outputDir,
        record.merge ? 1 : 0,
        record.mergeName,
        record.mergedOutput,
        record.status,
        record.error,
        record.createdAt,
        record.updatedAt,
      );
  }

  getBatch(batchId: string): PipelineBatchRecord | null {
    const row = this.db
      .prepare("SELECT * FROM pipeline_batches WHERE batch_id = ?")
      .get(batchId) as Record<string, unknown> | undefined;
    return row ? batchRow(row) : null;
  }

  listBatches(): PipelineBatchRecord[] {
    const rows = this.db
      .prepare("SELECT * FROM pipeline_batches ORDER BY created_at DESC")
      .all() as Array<Record<string, unknown>>;
    return rows.map(batchRow);
  }

  deleteBatch(batchId: string): void {
    this.db.prepare("DELETE FROM pipeline_batches WHERE batch_id = ?").run(batchId);
  }
}

function batchRow(row: Record<string, unknown>): PipelineBatchRecord {
  return {
    batchId: String(row.batch_id),
    outputDir: String(row.output_dir),
    merge: Number(row.merge) === 1,
    mergeName: row.merge_name ? String(row.merge_name) : null,
    mergedOutput: row.merged_output ? String(row.merged_output) : null,
    status: String(row.status),
    error: row.error ? String(row.error) : null,
    createdAt: Number(row.created_at),
    updatedAt: Number(row.updated_at),
  };
}

export function createDatabase(filePath: string): Store {
  const db = new DatabaseSync(filePath);
  db.exec("PRAGMA foreign_keys = ON");
  if (filePath !== ":memory:") db.exec("PRAGMA journal_mode = WAL");
  const store = new Store(db);
  store.migrate();
  return store;
}
