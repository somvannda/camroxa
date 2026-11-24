import type { Store } from "./database";
import {
  nextQueuedJob,
  updateQueueJob,
  type PipelineQueueItem,
} from "./pipeline-queue";

/**
 * Sequential queue runner.
 *
 * Rendering is injected so the orchestrator stays testable and the Electron
 * layer owns the editor/export details. Rules from the pipeline contract:
 * one active render, failure isolation (one item fails, the rest continue),
 * cancel between items, and a specific error on every failed row.
 */

/**
 * Thrown by a render port when the user cancelled the batch. The runner records
 * `cancelled` instead of `failed`, so a cancel never looks like a bug.
 */
export class PipelineCancelledError extends Error {
  constructor(message = "The render was cancelled.") {
    super(message);
    this.name = "PipelineCancelledError";
  }
}

export interface PipelineRunnerDeps {
  store: Store;
  render: (job: PipelineQueueItem) => Promise<{ output: string }>;
  /** Post-processing for a batch (merge). */
  merge?: (outputs: string[], batchId: string) => Promise<{ output: string }>;
  /** Merge only when the batch asked for it. Defaults to true. */
  shouldMerge?: (batchId: string) => boolean;
  /** Return true to stop before the next item; queued rows stay queued. */
  shouldStop?: () => boolean;
  onUpdate?: (job: PipelineQueueItem) => void;
}

export interface PipelineMergeSummary {
  batchId: string;
  output: string;
}

export interface PipelineRunSummary {
  done: number;
  failed: number;
  cancelled: number;
  stopped: boolean;
  outputs: string[];
  merged: PipelineMergeSummary[];
}

export async function runPipelineQueue(deps: PipelineRunnerDeps): Promise<PipelineRunSummary> {
  const summary: PipelineRunSummary = {
    done: 0,
    failed: 0,
    cancelled: 0,
    stopped: false,
    outputs: [],
    merged: [],
  };
  const outputsByBatch = new Map<string, string[]>();

  for (;;) {
    if (deps.shouldStop?.()) {
      summary.stopped = true;
      break;
    }
    const job = nextQueuedJob(deps.store);
    if (!job) break;

    const startedAt = Date.now();
    updateQueueJob(deps.store, job.id, {
      status: "rendering",
      stage: "rendering",
      progress: 0,
      startedAt,
    });
    deps.onUpdate?.({ ...job, status: "rendering", stage: "rendering", progress: 0 });

    try {
      const result = await deps.render(job);
      if (!result.output) throw new Error("The renderer returned no output.");
      updateQueueJob(deps.store, job.id, {
        status: "done",
        stage: "done",
        progress: 100,
        error: null,
        output: result.output,
      });
      summary.done += 1;
      summary.outputs.push(result.output);
      const batchOutputs = outputsByBatch.get(job.batchId) ?? [];
      batchOutputs.push(result.output);
      outputsByBatch.set(job.batchId, batchOutputs);
      deps.onUpdate?.({
        ...job,
        status: "done",
        stage: "done",
        progress: 100,
        error: null,
        output: result.output,
      });
    } catch (error) {
      if (error instanceof PipelineCancelledError) {
        updateQueueJob(deps.store, job.id, {
          status: "cancelled",
          stage: "cancelled",
          error: error.message,
          elapsedMs: Date.now() - startedAt,
        });
        summary.cancelled += 1;
        deps.onUpdate?.({
          ...job,
          status: "cancelled",
          stage: "cancelled",
          error: error.message,
        });
        summary.stopped = true;
        break;
      }
      const message = error instanceof Error ? error.message : String(error);
      updateQueueJob(deps.store, job.id, {
        status: "failed",
        stage: "failed",
        error: message,
        elapsedMs: Date.now() - startedAt,
      });
      summary.failed += 1;
      deps.onUpdate?.({ ...job, status: "failed", stage: "failed", error: message });
    }
  }

  if (deps.merge) {
    for (const [batchId, outputs] of outputsByBatch) {
      if (outputs.length < 2) continue;
      if (deps.shouldMerge && !deps.shouldMerge(batchId)) continue;
      const result = await deps.merge(outputs, batchId);
      if (result.output) summary.merged.push({ batchId, output: result.output });
    }
  }

  return summary;
}
