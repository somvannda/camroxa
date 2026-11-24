import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";

describe("database", () => {
  it("migrates and stores metadata", () => {
    const store = createDatabase(":memory:");
    store.setMeta("schema", "2.0.0");
    expect(store.getMeta("schema")).toBe("2.0.0");
    store.close();
  });

  it("stores templates and pipeline jobs", () => {
    const store = createDatabase(":memory:");
    const now = Date.now();
    store.upsertTemplate({
      id: "tpl-1",
      name: "Night Drive",
      kind: "long",
      schemaVersion: 2,
      path: "templates/tpl-1/template.json",
      thumbnailPath: null,
      createdAt: now,
      updatedAt: now,
    });
    expect(store.listTemplates("long")).toHaveLength(1);

    store.createJob({
      id: "job-1",
      batchId: "batch-1",
      status: "queued",
      stage: "render",
      progress: 0,
      payload: "{}",
      error: null,
      createdAt: now,
      updatedAt: now,
    });
    store.updateJob("job-1", { status: "rendering", progress: 0.5 });
    const jobs = store.listJobs();
    expect(jobs[0]?.status).toBe("rendering");
    expect(jobs[0]?.progress).toBe(0.5);
    store.close();
  });

  it("stores render timing and output metadata", () => {
    const store = createDatabase(":memory:");
    const now = Date.now();
    store.createJob({
      id: "job-timed",
      batchId: "batch-1",
      status: "queued",
      stage: "queued",
      progress: 0,
      payload: "{}",
      error: null,
      createdAt: now,
      updatedAt: now,
    });
    store.updateJob("job-timed", {
      status: "done",
      progress: 100,
      outputPath: "C:/runs/1. Song.mp4",
      startedAt: now,
      elapsedMs: 892_000,
      durationSec: 267.2,
      frames: 8017,
    });
    expect(store.listJobs()[0]).toMatchObject({
      status: "done",
      outputPath: "C:/runs/1. Song.mp4",
      startedAt: now,
      elapsedMs: 892_000,
      durationSec: 267.2,
      frames: 8017,
    });
    store.close();
  });

  it("upgrades an existing v1 templates table in place", () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-db-"));
    const file = path.join(directory, "camxora.db");
    try {
      const legacy = new DatabaseSync(file);
      legacy.exec(`
        CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL);
        CREATE TABLE templates (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          kind TEXT NOT NULL,
          schema_version INTEGER NOT NULL DEFAULT 2,
          path TEXT NOT NULL,
          thumbnail_path TEXT,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        );
        INSERT INTO schema_migrations (version, applied_at) VALUES (1, 0);
        INSERT INTO templates (id, name, kind, schema_version, path, thumbnail_path, created_at, updated_at)
          VALUES ('tpl-old', 'Old Template', 'video', 1, 'templates/tpl-old/template.json', NULL, 1, 1);
      `);
      legacy.close();

      const store = createDatabase(file);
      const migrated = store.listTemplates();
      expect(migrated).toHaveLength(1);
      expect(migrated[0]?.marketplaceItemId).toBeNull();

      store.upsertTemplate({
        id: "tpl-old",
        name: "Old Template",
        kind: "video",
        schemaVersion: 2,
        path: "templates/tpl-old/template.json",
        thumbnailPath: null,
        marketplaceItemId: "item-1",
        createdAt: 1,
        updatedAt: 2,
      });
      expect(store.findTemplateByMarketplaceItem("item-1")?.id).toBe("tpl-old");
      store.close();
    } finally {
      fs.rmSync(directory, { recursive: true, force: true });
    }
  });
});
