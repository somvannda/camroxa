import type { ConnectionOptions, Queue as BullQueue, Worker as BullWorker } from "bullmq";
import { config } from "./config.js";

/** Runs one job, identified by its `jobs` row id. Must not throw for control flow. */
export type JobHandler = (jobId: string) => Promise<void>;

export interface JobQueue {
  readonly driver: "memory" | "redis";
  /**
   * True when jobs are handed to a consumer instead of running inline in the
   * request. Callers use this to decide whether a submission must carry a
   * serializable descriptor.
   */
  readonly async: boolean;
  /** Verify the backend is reachable so a misconfigured queue fails at boot. */
  ping(): Promise<void>;
  enqueue(jobId: string): Promise<void>;
  start(handler: JobHandler): void;
  /** Wait (bounded) for the job currently being consumed, for graceful shutdown. */
  drain(timeoutMs?: number): Promise<void>;
  close(): Promise<void>;
}

/**
 * Default driver: no queue at all. A job runs inline in the process that
 * accepted the request (see `runClipJobWithRetry` / `runResultJobWithRetry`),
 * which is exactly the pre-R4 behaviour — so leaving `QUEUE_DRIVER` unset
 * changes nothing.
 */
function memoryQueue(): JobQueue {
  return {
    driver: "memory",
    async: false,
    async ping() {},
    async enqueue() {},
    start() {},
    async drain() {},
    async close() {},
  };
}

const QUEUE_NAME = "musicapi-jobs";

/**
 * Redis-backed work list via BullMQ. Job ids (not payloads) travel through
 * Redis — the `jobs` table stays the system of record, so a consumer resolves
 * the row and its `payload` descriptor before running it. Redis therefore only
 * has to answer "what still needs doing", and a restart or a second node can
 * pick up anything a dead consumer left behind.
 */
async function redisQueue(redisUrl: string, concurrency: number): Promise<JobQueue> {
  // Imported lazily so the default (in-memory) driver never loads Redis code.
  const { Queue, Worker } = await import("bullmq");

  // BullMQ owns the sockets. It needs connections that never give up on a
  // command (a rejected request would surface as a failed job instead of a
  // retry), and giving it options rather than one shared connection keeps the
  // Queue and the Worker on separate connections — sharing a single one between
  // them is what BullMQ warns against.
  const connection: ConnectionOptions = {
    url: redisUrl,
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
  };

  const queue: BullQueue = new Queue(QUEUE_NAME, { connection });
  // Connection errors are re-emitted on the queue; with no listener that
  // becomes an unhandled 'error' event and takes the process down.
  queue.on("error", (e: Error) => console.error(`[queue] redis error: ${e.message}`));
  let worker: BullWorker | null = null;

  return {
    driver: "redis",
    async: true,

    async ping() {
      // Bounded on purpose: ioredis retries a broken connection forever, so a
      // mistyped REDIS_URL would otherwise hang boot instead of reporting itself.
      const unreachable = new Promise<never>((_, reject) => {
        setTimeout(
          () => reject(new Error(`Redis at ${redisUrl} was not ready within 5s.`)),
          5_000,
        ).unref();
      });
      await Promise.race([queue.waitUntilReady(), unreachable]);
    },

    async enqueue(jobId) {
      try {
        await queue.add("job", { jobId }, {
          jobId,
          // Cross-account retry already happens inside the job body, so a
          // BullMQ-level retry would only duplicate work.
          attempts: 1,
          // Keep finished entries around briefly: an id that is still known
          // deduplicates a redundant enqueue (e.g. two nodes recovering the
          // same row at boot), then Redis reclaims the memory.
          removeOnComplete: { age: 3_600, count: 10_000 },
          removeOnFail: { age: 86_400, count: 10_000 },
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!/already exists/i.test(msg)) throw e;
        console.warn(`[queue] job ${jobId} is already queued, skipping duplicate enqueue.`);
      }
    },

    start(handler) {
      worker = new Worker(
        QUEUE_NAME,
        async (entry) => {
          await handler(String(entry?.data?.jobId ?? ""));
        },
        { connection, concurrency },
      );
      worker.on("error", (e: Error) => console.error(`[queue] worker error: ${e.message}`));
      worker.on("failed", (entry, err) =>
        console.error(`[queue] job ${entry?.id} failed: ${err instanceof Error ? err.message : err}`),
      );
    },

    async drain(timeoutMs = 30_000) {
      const active = worker;
      if (!active) return;
      worker = null;
      console.log("[queue] draining in-flight queued job(s)...");
      // `close()` resolves once the job currently being consumed finishes, which
      // is the queued counterpart of `drainJobs()` for inline jobs.
      await Promise.race([
        active.close(),
        new Promise((resolve) => setTimeout(resolve, timeoutMs)),
      ]);
    },

    async close() {
      // The worker's connection is released by `drain()`; this closes the
      // queue's own connection.
      await queue.close();
    },
  };
}

export async function createJobQueue(): Promise<JobQueue> {
  if (config.queue.driver !== "redis") return memoryQueue();
  return redisQueue(config.queue.redisUrl, config.queue.concurrency);
}
