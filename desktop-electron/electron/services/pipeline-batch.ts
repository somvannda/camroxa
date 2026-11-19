import type { Store } from "./database";
import {
  listQueue,
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
export interface PipelineRunnerDeps {
  store: Store;
  render: (job: PipelineQueueItem) => Promise<{ output: string }>;
  /** Optional post-processing for the batch (merge/reel). Not used yet. */
  merge?: (outputs: string[], batchId: string) => Promise<{ output: string }>;
  /** Return true to stop before the next item; queued rows stay queued. */
  shouldStop?: () => boolean;
  onUpdate?: (job: PipelineQueueItem) => void;
}

export interface PipelineRunSummary {
  done: number;
  failed: number;
  stopped: boolean;
  outputs: string[];
}

export async function runPipelineQueue(deps: PipelineRunnerDeps): Promise<PipelineRunSummary> {
  const summary: PipelineRunSummary = { done: 0, failed: 0, stopped: false, outputs: [] };

  for (;;) {
    if (deps.shouldStop?.()) {
      summary.stopped = true;
      break;
    }
    const job = nextQueuedJob(deps.store);
    if (!job) break;

    updateQueueJob(deps.store, job.id, { status: "rendering", stage: "rendering", progress: 0 });
    deps.onUpdate?.({ ...job, status: "rendering", stage: "rendering", progress: 0 });

    try {
      const result = await deps.render(job);
      if (!result.output) throw new Error("The renderer returned no output.");
      updateQueueJob(deps.store, job.id, {
        status: "done",
        stage: "done",
        progress: 100,
        error: null,
      });
      summary.done += 1;
      summary.outputs.push(result.output);
      deps.onUpdate?.({ ...job, status: "done", stage: "done", progress: 100, error: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      updateQueueJob(deps.store, job.id, {
        status: "failed",
        stage: "failed",
        error: message,
      });
      summary.failed += 1;
      deps.onUpdate?.({ ...job, status: "failed", stage: "failed", error: message });
    }
  }

  if (deps.merge && summary.outputs.length > 1) {
    const batchId = listQueue(deps.store).find((job) => job.status === "done")?.batchId;
    if (batchId) {
      await deps.merge(summary.outputs, batchId);
    }
  }

  return summary;
}
