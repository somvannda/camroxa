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
});
