import { describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";
import {
  clearFinishedJobs,
  enqueuePipelineJobs,
  listQueue,
  nextQueuedJob,
  reconcileInterruptedJobs,
  retryableJobs,
  updateQueueJob,
  type PipelineQueueInput,
} from "../../electron/services/pipeline-queue";

function item(overrides: Partial<PipelineQueueInput> = {}): PipelineQueueInput {
  return {
    batchId: "batch-1",
    branch: "long",
    templateId: "night-drive",
    audioPath: "C:/runs/song-1.mp3",
    outputDir: "C:/runs/out",
    title: "Song",
    artist: "Artist",
    album: "Album",
    ...overrides,
  };
}

describe("pipeline queue", () => {
  it("enqueues and lists jobs in order", () => {
    const store = createDatabase(":memory:");
    const created = enqueuePipelineJobs(store, [
      item(),
      item({ audioPath: "C:/runs/song-2.mp3", branch: "reel" }),
    ]);
    expect(created).toHaveLength(2);
    const list = listQueue(store);
    expect(list.map((job) => job.audioPath)).toEqual([
      "C:/runs/song-1.mp3",
      "C:/runs/song-2.mp3",
    ]);
    expect(list[0]).toMatchObject({ status: "queued", stage: "queued", progress: 0 });
    store.close();
  });

  it("deduplicates identical work but allows a retry after failure", () => {
    const store = createDatabase(":memory:");
    const first = enqueuePipelineJobs(store, [item()]);
    expect(first).toHaveLength(1);
    expect(enqueuePipelineJobs(store, [item()])).toHaveLength(0);

    updateQueueJob(store, first[0].id, { status: "failed", stage: "render", error: "boom" });
    const retry = enqueuePipelineJobs(store, [item()]);
    expect(retry).toHaveLength(1);
    expect(retry[0].id).not.toBe(first[0].id);
    store.close();
  });

  it("returns the next queued job and updates stage/progress", () => {
    const store = createDatabase(":memory:");
    const [job] = enqueuePipelineJobs(store, [item()]);
    expect(nextQueuedJob(store)?.id).toBe(job.id);
    updateQueueJob(store, job.id, { status: "rendering", stage: "rendering", progress: 12 });
    expect(nextQueuedJob(store)).toBeNull();
    expect(listQueue(store)[0]).toMatchObject({ status: "rendering", progress: 12 });
    store.close();
  });

  it("clears done and cancelled jobs only", () => {
    const store = createDatabase(":memory:");
    const jobs = enqueuePipelineJobs(store, [
      item(),
      item({ audioPath: "C:/runs/song-2.mp3" }),
      item({ audioPath: "C:/runs/song-3.mp3" }),
    ]);
    updateQueueJob(store, jobs[0].id, { status: "done" });
    updateQueueJob(store, jobs[1].id, { status: "cancelled" });
    expect(clearFinishedJobs(store)).toBe(2);
    expect(listQueue(store).map((job) => job.id)).toEqual([jobs[2].id]);
    store.close();
  });

  it("ignores malformed payloads", () => {
    const store = createDatabase(":memory:");
    store.createJob({
      id: "bad",
      batchId: "batch",
      status: "queued",
      stage: "queued",
      progress: 0,
      payload: "{}",
      error: null,
      createdAt: 0,
      updatedAt: 0,
    });
    expect(listQueue(store)).toEqual([]);
    store.close();
  });

  it("recovers rows interrupted by an app restart", () => {
    const store = createDatabase(":memory:");
    store.upsertBatch({
      batchId: "batch-1",
      outputDir: "C:/runs/out",
      merge: true,
      mergeName: null,
      mergedOutput: null,
      status: "running",
      error: null,
      createdAt: 0,
      updatedAt: 0,
    });
    const [job] = enqueuePipelineJobs(store, [item()]);
    updateQueueJob(store, job.id, { status: "encoding", stage: "encoding", progress: 60 });

    const recovered = reconcileInterruptedJobs(store);
    expect(recovered).toBe(1);
    const row = listQueue(store)[0];
    expect(row.status).toBe("failed");
    expect(row.error).toMatch(/app closed/i);
    expect(store.getBatch("batch-1")?.status).toBe("failed");
    // A reconciled row is retryable again.
    expect(retryableJobs(store, "batch-1")).toHaveLength(1);
    store.close();
  });
});
