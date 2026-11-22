import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";
import {
  enqueuePipelineJobs,
  listQueue,
  retryableJobs,
  updateQueueJob,
  type PipelineQueueInput,
} from "../../electron/services/pipeline-queue";
import {
  PipelineRunner,
  createProgressThrottle,
  deriveBatchStatus,
  queueProgressFor,
  queueStageFor,
  type PipelineOrchestratorDeps,
} from "../../electron/services/pipeline-orchestrator";
import { PipelineCancelledError } from "../../electron/services/pipeline-batch";
import { buildPipelineTemplate } from "../../electron/services/pipeline-templates";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-pipeline-orch-"));
afterAll(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

const snapshot = {
  project: { name: "Orchestrator template", width: 320, height: 180, fps: 30, duration: 2 },
  nodes: [],
};

function templateSource(id = "template-a") {
  return {
    id,
    name: "Orchestrator template",
    projectJson: JSON.stringify(snapshot),
    pipeline: buildPipelineTemplate({
      name: "Orchestrator template",
      snapshot,
      bindings: { audio: { mode: "replace" } },
    }),
  };
}

function item(overrides: Partial<PipelineQueueInput> = {}): PipelineQueueInput {
  return {
    batchId: "batch-1",
    branch: "long",
    templateId: "template-a",
    audioPath: path.join(root, "song-1.mp3"),
    outputDir: root,
    title: "Song One",
    ...overrides,
  };
}

function baseDeps(overrides: Partial<PipelineOrchestratorDeps> = {}): PipelineOrchestratorDeps {
  return {
    store: createDatabase(":memory:"),
    readTemplate: () => templateSource(),
    probeDuration: async () => 2,
    probeMedia: async () => ({ durationSec: 2, width: 320, height: 180, videoCodec: "h264" }),
    render: async (input) => ({ output: path.join(root, `${input.outputName}.mp4`) }),
    ...overrides,
  };
}

function seedBatch(
  deps: PipelineOrchestratorDeps,
  batchId: string,
  merge: boolean,
): void {
  deps.store.upsertBatch({
    batchId,
    outputDir: root,
    merge,
    mergeName: null,
    mergedOutput: null,
    status: "idle",
    error: null,
    createdAt: 0,
    updatedAt: 0,
  });
}

describe("pipeline orchestration helpers", () => {
  it("maps exporter stages to queue stages and percentages", () => {
    expect(queueStageFor("rendering frames")).toBe("rendering");
    expect(queueStageFor("encoding video")).toBe("encoding");
    expect(queueStageFor("muxing audio")).toBe("encoding");
    expect(queueStageFor("joining segments")).toBe("encoding");

    expect(queueProgressFor(0, 60, "rendering frames")).toBe(0);
    expect(queueProgressFor(60, 60, "rendering frames")).toBe(85);
    expect(queueProgressFor(60, 60, "muxing audio")).toBe(99);
    expect(queueProgressFor(60, 60, "loading ffmpeg core")).toBe(85);
  });

  it("throttles progress writes and never repeats a percentage", () => {
    let clock = 0;
    const throttle = createProgressThrottle(500, () => clock);
    expect(throttle.shouldWrite(10)).toBe(true);
    clock = 100;
    expect(throttle.shouldWrite(20)).toBe(false);
    clock = 600;
    expect(throttle.shouldWrite(20)).toBe(true);
    clock = 1200;
    expect(throttle.shouldWrite(20)).toBe(false);
    expect(throttle.shouldWrite(20, true)).toBe(true);
  });

  it("derives a batch status from its rows", () => {
    expect(deriveBatchStatus([], false)).toBe("idle");
    expect(deriveBatchStatus([{ status: "queued" }], false)).toBe("running");
    expect(deriveBatchStatus([{ status: "done" }, { status: "rendering" }], false)).toBe("running");
    expect(deriveBatchStatus([{ status: "done" }, { status: "failed" }], false)).toBe("failed");
    expect(deriveBatchStatus([{ status: "cancelled" }], false)).toBe("cancelled");
    expect(deriveBatchStatus([{ status: "done" }], true)).toBe("merging");
  });
});

describe("pipeline orchestrator", () => {
  it("renders every queued row through the injected port", async () => {
    const rendered: string[] = [];
    const stages = new Set<string>();
    const deps = baseDeps({
      render: async (input) => {
        rendered.push(input.job.title);
        input.onProgress?.({ percent: 40, stage: "rendering" });
        input.onProgress?.({ percent: 92, stage: "encoding" });
        return { output: path.join(root, `${input.outputName}.mp4`) };
      },
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [item(), item({ audioPath: path.join(root, "song-2.mp3"), title: "Song Two" })]);
    const runner = new PipelineRunner({
      ...deps,
      onEvent: (event) => stages.add(event.reason),
    });

    const summary = await runner.run();
    expect(summary).toMatchObject({ done: 2, failed: 0, cancelled: 0 });
    expect(rendered).toEqual(["Song One", "Song Two"]);
    const rows = listQueue(deps.store);
    expect(rows.every((row) => row.status === "done")).toBe(true);
    expect(rows.every((row) => Boolean(row.output))).toBe(true);
    expect(stages.has("started")).toBe(true);
    expect(stages.has("done")).toBe(true);
    deps.store.close();
  });

  it("fails one row with a specific error and renders the next", async () => {
    const deps = baseDeps({
      readTemplate: (id) => {
        if (id === "missing") throw new Error("That video template does not exist.");
        return templateSource();
      },
      render: async (input) => ({ output: path.join(root, `${input.outputName}.mp4`) }),
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [
      item({ templateId: "missing", title: "Song One" }),
      item({ audioPath: path.join(root, "song-2.mp3"), title: "Song Two" }),
    ]);

    const summary = await new PipelineRunner(deps).run();
    expect(summary).toMatchObject({ done: 1, failed: 1 });
    const rows = listQueue(deps.store);
    const failed = rows.find((row) => row.status === "failed");
    expect(failed?.error).toMatch(/does not exist/);
    expect(rows.find((row) => row.status === "done")?.output).toBeTruthy();
    deps.store.close();
  });

  it("rejects a render that ffprobe cannot validate", async () => {
    const deps = baseDeps({
      probeMedia: async () => ({ durationSec: 0, width: null, height: null, videoCodec: null }),
      render: async (input) => ({ output: path.join(root, `${input.outputName}.mp4`) }),
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [item()]);
    const summary = await new PipelineRunner(deps).run();
    expect(summary.failed).toBe(1);
    expect(listQueue(deps.store)[0].status).toBe("failed");
    expect(listQueue(deps.store)[0].error).toMatch(/not a valid video/i);
    deps.store.close();
  });

  it("cancels the in-flight render and records the row as cancelled", async () => {
    let release: (() => void) | null = null;
    let notifyStarted: (() => void) | null = null;
    const started = new Promise<void>((resolve) => {
      notifyStarted = resolve;
    });
    const deps = baseDeps({
      render: async (input) => {
        input.registerCancel?.(() => release?.());
        notifyStarted?.();
        await new Promise<void>((done) => {
          release = done;
        });
        throw new PipelineCancelledError();
      },
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [item()]);
    const runner = new PipelineRunner(deps);
    const runPromise = runner.run();

    await started;
    runner.cancel();
    const summary = await runPromise;
    expect(summary).toMatchObject({ cancelled: 1, done: 0 });
    const row = listQueue(deps.store)[0];
    expect(row.status).toBe("cancelled");
    expect(row.output).toBeNull();
    deps.store.close();
  });

  it("merges only when the batch asks for it", async () => {
    const merges: Array<{ inputs: string[]; output: string }> = [];
    const deps = baseDeps({
      merge: async (inputs, output) => {
        merges.push({ inputs, output });
        return { output };
      },
      render: async (input) => ({ output: path.join(root, `${input.outputName}.mp4`) }),
    });
    seedBatch(deps, "batch-1", true);
    enqueuePipelineJobs(deps.store, [
      item(),
      item({ audioPath: path.join(root, "song-2.mp3"), title: "Song Two" }),
    ]);

    const summary = await new PipelineRunner(deps).run();
    expect(merges).toHaveLength(1);
    expect(merges[0].inputs).toHaveLength(2);
    expect(merges[0].output.startsWith(root)).toBe(true);
    expect(summary.merged).toHaveLength(1);
    const batch = deps.store.getBatch("batch-1");
    expect(batch?.mergedOutput).toBe(merges[0].output);
    deps.store.close();
  });

  it("does not merge a batch that did not request it", async () => {
    let calls = 0;
    const deps = baseDeps({
      merge: async (_inputs, output) => {
        calls += 1;
        return { output };
      },
      render: async (input) => ({ output: path.join(root, `${input.outputName}.mp4`) }),
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [
      item(),
      item({ audioPath: path.join(root, "song-2.mp3"), title: "Song Two" }),
    ]);
    await new PipelineRunner(deps).run();
    expect(calls).toBe(0);
    deps.store.close();
  });

  it("retries only the failed rows", async () => {
    let attempt = 0;
    const deps = baseDeps({
      render: async (input) => {
        attempt += 1;
        if (input.job.title === "Song One" && attempt === 1) throw new Error("decoder failed");
        return { output: path.join(root, `${input.outputName}.mp4`) };
      },
    });
    seedBatch(deps, "batch-1", false);
    enqueuePipelineJobs(deps.store, [
      item({ title: "Song One" }),
      item({ audioPath: path.join(root, "song-2.mp3"), title: "Song Two" }),
    ]);
    await new PipelineRunner(deps).run();

    const retryable = retryableJobs(deps.store, "batch-1");
    expect(retryable).toHaveLength(1);
    expect(retryable[0].title).toBe("Song One");

    enqueuePipelineJobs(
      deps.store,
      retryable.map((job) => ({
        batchId: job.batchId,
        branch: job.branch,
        templateId: job.templateId,
        audioPath: job.audioPath,
        outputDir: job.outputDir,
        title: job.title,
        merge: job.merge,
      })),
    );
    // A retry must not re-render the row that already succeeded.
    updateQueueJob(deps.store, retryable[0].id, { status: "cancelled" });
    const summary = await new PipelineRunner(deps).run();
    expect(summary).toMatchObject({ done: 1, failed: 0 });
    expect(attempt).toBe(3);
    deps.store.close();
  });
});
