import { describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";
import { enqueuePipelineJobs, listQueue, type PipelineQueueInput } from "../../electron/services/pipeline-queue";
import { runPipelineQueue } from "../../electron/services/pipeline-batch";

function item(index: number): PipelineQueueInput {
  return {
    batchId: "batch-1",
    branch: "long",
    templateId: "night-drive",
    audioPath: `C:/runs/song-${index}.mp3`,
    outputDir: "C:/runs/out",
    title: `Song ${index}`,
  };
}

describe("pipeline batch runner", () => {
  it("renders every queued item and records outputs", async () => {
    const store = createDatabase(":memory:");
    enqueuePipelineJobs(store, [item(1), item(2)]);
    const rendered: string[] = [];
    const summary = await runPipelineQueue({
      store,
      render: async (job) => {
        rendered.push(job.audioPath);
        return { output: `C:/runs/out/${job.title}.mp4` };
      },
    });
    expect(summary).toMatchObject({ done: 2, failed: 0, stopped: false });
    expect(rendered).toEqual(["C:/runs/song-1.mp3", "C:/runs/song-2.mp3"]);
    expect(listQueue(store).every((job) => job.status === "done")).toBe(true);
    store.close();
  });

  it("isolates a failure and continues with the rest", async () => {
    const store = createDatabase(":memory:");
    enqueuePipelineJobs(store, [item(1), item(2), item(3)]);
    const summary = await runPipelineQueue({
      store,
      render: async (job) => {
        if (job.audioPath.endsWith("song-2.mp3")) throw new Error("decoder failed");
        return { output: `C:/runs/out/${job.title}.mp4` };
      },
    });
    expect(summary).toMatchObject({ done: 2, failed: 1 });
    const rows = listQueue(store);
    expect(rows.map((job) => job.status)).toEqual(["done", "failed", "done"]);
    expect(rows[1]?.error).toBe("decoder failed");
    store.close();
  });

  it("stops between items and leaves the rest queued", async () => {
    const store = createDatabase(":memory:");
    enqueuePipelineJobs(store, [item(1), item(2), item(3)]);
    let calls = 0;
    const summary = await runPipelineQueue({
      store,
      shouldStop: () => calls >= 1,
      render: async (job) => {
        calls += 1;
        return { output: `C:/runs/out/${job.title}.mp4` };
      },
    });
    expect(summary).toMatchObject({ done: 1, stopped: true });
    expect(listQueue(store).map((job) => job.status)).toEqual(["done", "queued", "queued"]);
    store.close();
  });

  it("merges the batch when more than one output exists", async () => {
    const store = createDatabase(":memory:");
    enqueuePipelineJobs(store, [item(1), item(2)]);
    let merged: string[] = [];
    await runPipelineQueue({
      store,
      render: async (job) => ({ output: `C:/runs/out/${job.title}.mp4` }),
      merge: async (outputs) => {
        merged = outputs;
        return { output: "C:/runs/out/merged.mp4" };
      },
    });
    expect(merged).toHaveLength(2);
    store.close();
  });

  it("does not merge a single output", async () => {
    const store = createDatabase(":memory:");
    enqueuePipelineJobs(store, [item(1)]);
    let calls = 0;
    await runPipelineQueue({
      store,
      render: async (job) => ({ output: `C:/runs/out/${job.title}.mp4` }),
      merge: async () => {
        calls += 1;
        return { output: "C:/runs/out/merged.mp4" };
      },
    });
    expect(calls).toBe(0);
    store.close();
  });
});
