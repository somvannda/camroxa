import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  DownloadCoordinator,
  type DownloadFetchResult,
  type DownloadIo,
  type DownloadSink,
  type DownloadSyncReport,
} from "../../electron/services/download-coordinator";

const ROOT = path.resolve("/camxora-root/suno");

function waitFor(predicate: () => boolean, timeoutMs = 4_000): Promise<void> {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (predicate()) {
        resolve();
        return;
      }
      if (Date.now() - started > timeoutMs) {
        reject(new Error("Timed out waiting for the download state"));
        return;
      }
      setTimeout(tick, 5);
    };
    tick();
  });
}

class FakeSink implements DownloadSink {
  private chunks: Uint8Array[] = [];
  committed = false;
  aborted = false;

  constructor(
    private readonly target: string,
    private readonly files: Map<string, Uint8Array>,
  ) {}

  async write(chunk: Uint8Array): Promise<void> {
    if (this.aborted) throw new Error("The sink was aborted.");
    this.chunks.push(chunk);
  }

  async commit(): Promise<void> {
    this.committed = true;
    const total = this.chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    this.files.set(this.target, merged);
  }

  async abort(): Promise<void> {
    this.aborted = true;
    this.chunks = [];
    this.files.delete(this.target);
  }

  abortSync(): void {
    this.aborted = true;
    this.chunks = [];
    this.files.delete(this.target);
  }
}

function fakeIo() {
  const files = new Map<string, Uint8Array>();
  const sinks: FakeSink[] = [];
  const io: DownloadIo = {
    ensureDir: async () => undefined,
    fileSize: async (filePath) => files.get(filePath)?.byteLength ?? null,
    createSink: async (targetPath) => {
      const sink = new FakeSink(targetPath, files);
      sinks.push(sink);
      return sink;
    },
  };
  return { io, files, sinks };
}

function payload(items: unknown[]) {
  return { items };
}

function item(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    task_id: "task-1",
    song_id: "song-1",
    batch_id: "batch-1",
    title: "Night Drive",
    track_number: 1,
    primary: {
      download_url: "https://cdn.example.test/a.mp3",
      downloaded: false,
      output_dir: null,
      target_path: path.join(ROOT, "01 Night Drive.mp3"),
    },
    ...overrides,
  };
}

function bodyOf(text: string, chunkSize = 4): AsyncIterable<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  return {
    async *[Symbol.asyncIterator]() {
      for (let offset = 0; offset < bytes.length; offset += chunkSize) {
        yield bytes.slice(offset, offset + chunkSize);
      }
    },
  };
}

function okResponse(text: string, chunkSize = 4): DownloadFetchResult {
  return {
    status: 200,
    ok: true,
    totalBytes: new TextEncoder().encode(text).byteLength,
    body: bodyOf(text, chunkSize),
  };
}

interface HarnessOptions {
  items: unknown[];
  download: (url: string, signal: AbortSignal, call: number) => Promise<DownloadFetchResult>;
  concurrency?: number;
  maxAttempts?: number;
  root?: string;
  report?: (items: DownloadSyncReport[]) => Promise<void>;
}

function harness(options: HarnessOptions) {
  const { io, files, sinks } = fakeIo();
  const events: string[] = [];
  let downloadCalls = 0;
  const coordinator = new DownloadCoordinator({
    fetchPending: async () => payload(options.items),
    fetchDownload: async (url, signal) => {
      downloadCalls += 1;
      return options.download(url, signal, downloadCalls);
    },
    io,
    resolveRoot: () => ({ root: options.root ?? ROOT, managed: true }),
    reportDownloads: options.report,
    reportDelayMs: 1,
    emit: (event) => events.push(`${event.reason}:${event.key ?? "all"}`),
    allowLoopbackHttp: () => true,
    concurrency: options.concurrency ?? 2,
    maxAttempts: options.maxAttempts ?? 3,
    retryDelaysMs: [1, 1],
    sleep: async () => undefined,
    idlePollMs: 1_000_000,
    pendingPollMs: 1_000_000,
    progressIntervalMs: 0,
  });
  return {
    coordinator,
    files,
    sinks,
    events,
    calls: () => downloadCalls,
  };
}

describe("download coordinator", () => {
  it("downloads pending targets to their resolved paths with byte progress", async () => {
    const test = harness({
      items: [
        item({ task_id: "a", primary: { download_url: "https://cdn.test/a.mp3", target_path: path.join(ROOT, "a.mp3") } }),
        item({ task_id: "b", primary: { download_url: "https://cdn.test/b.mp3", target_path: path.join(ROOT, "b.mp3") } }),
      ],
      download: async () => okResponse("hello world"),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items.every((entry) => entry.state === "done"));

    const snapshot = test.coordinator.snapshot();
    expect(snapshot.items).toHaveLength(2);
    expect(snapshot.active).toBe(0);
    expect(snapshot.root).toBe(ROOT);
    expect(snapshot.items[0].receivedBytes).toBe(11);
    expect(snapshot.items[0].totalBytes).toBe(11);
    expect(snapshot.items[0].percent).toBe(100);
    expect(test.files.get(path.join(ROOT, "a.mp3"))).toBeDefined();
    expect(test.files.get(path.join(ROOT, "b.mp3"))).toBeDefined();
    expect(test.events).toContain("started:a::primary");
    expect(test.events).toContain("done:a::primary");
    test.coordinator.dispose();
  });

  it("never fetches the same task twice when the server repeats it", async () => {
    const test = harness({
      items: [item({ task_id: "dup" })],
      download: async () => okResponse("abc"),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "done");
    await test.coordinator.pollNow();
    await test.coordinator.pollNow();
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(test.calls()).toBe(1);
    expect(test.coordinator.snapshot().items).toHaveLength(1);
    test.coordinator.dispose();
  });

  it("retries a 5xx with backoff and then succeeds", async () => {
    const test = harness({
      items: [item({ task_id: "retry" })],
      download: async (_url, _signal, call) =>
        call === 1
          ? { status: 500, ok: false, totalBytes: null, body: null }
          : okResponse("recovered"),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "done", 5_000);

    const entry = test.coordinator.snapshot().items[0];
    expect(entry.state).toBe("done");
    expect(entry.attempts).toBe(2);
    expect(entry.receivedBytes).toBe(9);
    expect(test.calls()).toBe(2);
    test.coordinator.dispose();
  });

  it("stops retrying at the attempt limit and keeps a specific error", async () => {
    const test = harness({
      items: [item({ task_id: "always-500" })],
      download: async () => ({ status: 503, ok: false, totalBytes: null, body: null }),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "failed");

    const entry = test.coordinator.snapshot().items[0];
    expect(entry.attempts).toBe(3);
    expect(entry.errorCode).toBe("DOWNLOAD_HTTP_503");
    expect(entry.error).toContain("HTTP 503");
    expect(test.calls()).toBe(3);
    test.coordinator.dispose();
  });

  it("treats a gone URL as a permanent error and retries only on demand", async () => {
    const test = harness({
      items: [item({ task_id: "gone" })],
      download: async () => ({ status: 404, ok: false, totalBytes: null, body: null }),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "failed");

    const entry = test.coordinator.snapshot().items[0];
    expect(entry.errorCode).toBe("DOWNLOAD_URL_GONE");
    expect(test.calls()).toBe(1);

    const outcome = test.coordinator.retry("gone::primary");
    expect(outcome.ok).toBe(true);
    await waitFor(() => test.calls() === 2);
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "failed");
    expect(test.calls()).toBe(2);
    test.coordinator.dispose();
  });

  it("cancels an in-flight stream and deletes the partial file", async () => {
    let startStream = () => undefined as void;
    const streaming = new Promise<void>((resolve) => {
      startStream = resolve;
    });
    const test = harness({
      items: [item({ task_id: "cancel" })],
      download: async (_url, signal) => {
        startStream();
        return {
          status: 200,
          ok: true,
          totalBytes: 1_000,
          body: {
            async *[Symbol.asyncIterator]() {
              yield new Uint8Array(10);
              await new Promise((_resolve, reject) => {
                signal.addEventListener(
                  "abort",
                  () => {
                    const error = new Error("aborted");
                    error.name = "AbortError";
                    reject(error);
                  },
                  { once: true },
                );
              });
            },
          },
        };
      },
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await streaming;
    await waitFor(() => test.coordinator.snapshot().items[0]?.receivedBytes === 10);

    const entry = test.coordinator.snapshot().items[0];
    expect(entry.state).toBe("downloading");
    expect(test.sinks[0].committed).toBe(false);

    expect(test.coordinator.cancel("cancel::primary").ok).toBe(true);
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "cancelled");
    await new Promise((resolve) => setTimeout(resolve, 20));

    const cancelled = test.coordinator.snapshot().items[0];
    expect(cancelled.receivedBytes).toBe(0);
    expect(cancelled.percent).toBeNull();
    expect(test.sinks[0].committed).toBe(false);
    expect(test.sinks[0].aborted).toBe(true);
    expect(test.files.size).toBe(0);
    test.coordinator.dispose();
  });

  it("pauses and resumes a queued download", async () => {
    let firstCall = 0;
    const test = harness({
      concurrency: 1,
      items: [item({ task_id: "pause" })],
      download: async (_url, signal) => {
        firstCall += 1;
        if (firstCall === 1) {
          return {
            status: 200,
            ok: true,
            totalBytes: 100,
            body: {
              async *[Symbol.asyncIterator]() {
                yield new Uint8Array(5);
                await new Promise((_resolve, reject) => {
                  signal.addEventListener(
                    "abort",
                    () => {
                      const error = new Error("aborted");
                      error.name = "AbortError";
                      reject(error);
                    },
                    { once: true },
                  );
                });
              },
            },
          };
        }
        return okResponse("complete");
      },
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.receivedBytes === 5);

    test.coordinator.stop();
    expect(test.coordinator.snapshot().paused).toBe(true);
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "queued");

    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "done");
    expect(test.coordinator.snapshot().items[0].receivedBytes).toBe(8);
    expect(test.calls()).toBe(2);
    test.coordinator.dispose();
  });

  it("reports a missing URL, a traversal target and a non-file target as failed rows", async () => {
    const test = harness({
      items: [
        item({
          task_id: "no-url",
          primary: { download_url: null, target_path: path.join(ROOT, "a.mp3") },
        }),
        item({
          task_id: "traversal",
          primary: { download_url: "https://cdn.test/b.mp3", target_path: `${ROOT}/../evil.mp3` },
        }),
        item({
          task_id: "folder",
          primary: { download_url: "https://cdn.test/c.mp3", target_path: `${ROOT}${path.sep}` },
        }),
      ],
      download: async () => okResponse("never"),
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items.length === 3);

    const items = test.coordinator.snapshot().items;
    const byTask = new Map(items.map((entry) => [entry.taskId, entry]));
    expect(byTask.get("no-url")?.errorCode).toBe("DOWNLOAD_URL_MISSING");
    expect(byTask.get("no-url")?.state).toBe("failed");
    expect(byTask.get("traversal")?.errorCode).toBe("DOWNLOAD_TARGET_UNSAFE");
    expect(byTask.get("folder")?.errorCode).toBe("DOWNLOAD_NOT_A_FILE");
    expect(test.calls()).toBe(0);
    expect(test.files.size).toBe(0);
    test.coordinator.dispose();
  });

  it("keeps at most the configured number of downloads in flight", async () => {
    let active = 0;
    let peak = 0;
    const test = harness({
      concurrency: 2,
      items: [
        item({ task_id: "one", primary: { download_url: "https://cdn.test/1", target_path: path.join(ROOT, "1.mp3") } }),
        item({ task_id: "two", primary: { download_url: "https://cdn.test/2", target_path: path.join(ROOT, "2.mp3") } }),
        item({ task_id: "three", primary: { download_url: "https://cdn.test/3", target_path: path.join(ROOT, "3.mp3") } }),
      ],
      download: async () => {
        active += 1;
        peak = Math.max(peak, active);
        await new Promise((resolve) => setTimeout(resolve, 20));
        active -= 1;
        return okResponse("ok");
      },
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items.every((entry) => entry.state === "done"));
    expect(peak).toBeLessThanOrEqual(2);
    expect(test.coordinator.snapshot().concurrency).toBe(2);
    test.coordinator.dispose();
  });

  it("acknowledges each finished target once through the sync port", async () => {
    const reports: DownloadSyncReport[] = [];
    const test = harness({
      items: [
        item({ task_id: "task-a", primary: { download_url: "https://cdn.test/a", target_path: path.join(ROOT, "a.mp3") } }),
        item({ task_id: "task-b", primary: { download_url: "https://cdn.test/b", target_path: path.join(ROOT, "b.mp3") } }),
        item({ task_id: "task-fail", primary: { download_url: "https://cdn.test/c", target_path: path.join(ROOT, "c.mp3") } }),
      ],
      download: async (url) => (url.endsWith("/c") ? { status: 404, ok: false, totalBytes: null, body: null } : okResponse("done")),
      report: async (items) => {
        reports.push(...items);
      },
    });
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items.every((entry) => entry.state !== "queued" && entry.state !== "downloading"));
    await waitFor(() => reports.length === 2);

    expect(reports.map((entry) => `${entry.taskId}:${entry.role}`).sort()).toEqual([
      "task-a:primary",
      "task-b:primary",
    ]);
    for (const entry of reports) expect(entry.outputDir).toBe(ROOT);

    await test.coordinator.pollNow();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(reports).toHaveLength(2);
    test.coordinator.dispose();
  });

  it("skips a file that is already on disk instead of downloading it again", async () => {
    const test = harness({
      items: [item({ task_id: "exists" })],
      download: async () => okResponse("network bytes"),
    });
    test.files.set(path.join(ROOT, "01 Night Drive.mp3"), new Uint8Array(42));
    test.coordinator.start();
    await test.coordinator.pollNow();
    await waitFor(() => test.coordinator.snapshot().items[0]?.state === "done");
    expect(test.calls()).toBe(0);
    expect(test.coordinator.snapshot().items[0].receivedBytes).toBe(42);
    test.coordinator.dispose();
  });
});
