/**
 * Main-process Suno download coordinator.
 *
 * Polls `GET /music/downloads/pending`, resolves every pending target into a
 * path under the device output root, and streams it to disk with bounded
 * concurrency. The renderer never downloads anything: it reads snapshots and
 * asks for retry/cancel/reveal through IPC.
 *
 * Everything that touches the network, the clock or the disk is injected, so the
 * state machine (dedupe, retry/backoff, cancel, containment) is unit-tested with
 * a fake fetcher and writer.
 *
 * Deliberate deviations from the 1.7.1 coordinator, documented in
 * `docs/electron-desktop/pages/04-PROGRESS.md`:
 * - the poll cadence (12 s idle, 4 s while work is pending) is unchanged, but it
 *   runs in the main process and keeps running while a modal or preview is open;
 * - a target is skipped when the file already exists, so a restart never
 *   re-downloads a track;
 * - a missing/invalid/gone URL becomes a failed row with a specific message
 *   instead of a silent skip.
 */
import path from "node:path";
import type {
  DownloadChangedEvent,
  DownloadChangedReason,
  DownloadItemInfo,
  DownloadSnapshot,
  DownloadTargetRole,
} from "../shared/types";
import {
  DOWNLOAD_URL_FORBIDDEN_MESSAGE,
  DOWNLOAD_URL_GONE_MESSAGE,
  DOWNLOAD_URL_MISSING_MESSAGE,
  normalizePendingDownloads,
  resolveDownloadTarget,
  targetKey,
  type PendingDownloadItem,
} from "./download-targets";

export interface DownloadFetchResult {
  status: number;
  ok: boolean;
  totalBytes: number | null;
  /** Async iterable of body chunks; null when the response has no body. */
  body: AsyncIterable<Uint8Array> | null;
}

export interface DownloadSink {
  write(chunk: Uint8Array): Promise<void>;
  /** Flush, close and atomically move the temp file into place. */
  commit(): Promise<void>;
  /** Close and delete the partial file. Safe to call twice. */
  abort(): Promise<void>;
  /** Quit path: delete the partial file before the process exits. */
  abortSync(): void;
}

export interface DownloadIo {
  ensureDir(directory: string): Promise<void>;
  createSink(targetPath: string): Promise<DownloadSink>;
  /** Existing file size, or null when the file is absent/empty/not a file. */
  fileSize(filePath: string): Promise<number | null>;
}

export interface DownloadRoot {
  root: string;
  managed: boolean;
}

/** One finished target, reported back through `POST /music/downloads/sync`. */
export interface DownloadSyncReport {
  taskId: string;
  role: DownloadTargetRole;
  outputDir: string;
}

export interface DownloadLogger {
  info(message: string, detail?: unknown): void;
  warn(message: string, detail?: unknown): void;
  error(message: string, detail?: unknown): void;
}

export interface DownloadCoordinatorOptions {
  /** One authenticated `GET /music/downloads/pending` call. */
  fetchPending: (limit: number) => Promise<unknown>;
  fetchDownload: (url: string, signal: AbortSignal) => Promise<DownloadFetchResult>;
  io: DownloadIo;
  resolveRoot: () => DownloadRoot;
  /** Acknowledge finished targets so the server stops listing them as pending. */
  reportDownloads?: (items: DownloadSyncReport[]) => Promise<void>;
  /** Debounce for the sync call; tests shorten it. */
  reportDelayMs?: number;
  emit?: (event: DownloadChangedEvent) => void;
  now?: () => number;
  logger?: DownloadLogger;
  allowLoopbackHttp?: () => boolean;
  concurrency?: number;
  maxAttempts?: number;
  retryDelaysMs?: number[];
  idlePollMs?: number;
  pendingPollMs?: number;
  progressIntervalMs?: number;
  pendingLimit?: number;
  doneRetentionMs?: number;
  failedRetentionMs?: number;
  maxItems?: number;
  /** Swappable in tests so backoff does not slow the suite down. */
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

export interface DownloadActionFailure {
  code: string;
  message: string;
}

export type DownloadActionResult = { ok: true } | { ok: false; error: DownloadActionFailure };

interface TrackedDownload {
  info: DownloadItemInfo;
  url: string | null;
  createdAt: number;
  controller: AbortController | null;
  sink: DownloadSink | null;
  cancelReason: "user" | "pause" | null;
}

const DEFAULT_CONCURRENCY = 2;
const MAX_CONCURRENCY = 3;
const DEFAULT_MAX_ATTEMPTS = 3;
const DEFAULT_RETRY_DELAYS = [750, 2_000];
const DEFAULT_IDLE_POLL_MS = 12_000;
const DEFAULT_PENDING_POLL_MS = 4_000;
const DEFAULT_PROGRESS_INTERVAL_MS = 400;
const DEFAULT_PENDING_LIMIT = 24;
const DEFAULT_DONE_RETENTION_MS = 60_000;
const DEFAULT_FAILED_RETENTION_MS = 10 * 60_000;
const DEFAULT_MAX_ITEMS = 200;
const REQUEST_POLL_MIN_GAP_MS = 1_500;

export class DownloadError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = "DownloadError";
  }
}

function abortError(): Error {
  const error = new Error("The download was cancelled.");
  error.name = "AbortError";
  return error;
}

function defaultSleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError());
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, Math.max(0, ms));
    function onAbort() {
      clearTimeout(timer);
      reject(abortError());
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function clampConcurrency(value: number | undefined): number {
  if (!Number.isFinite(value) || value === undefined) return DEFAULT_CONCURRENCY;
  return Math.min(MAX_CONCURRENCY, Math.max(1, Math.trunc(value)));
}

function percentOf(received: number, total: number | null): number | null {
  if (total === null || total <= 0) return null;
  return Math.min(100, Math.max(0, Math.round((received / total) * 100)));
}

export class DownloadCoordinator {
  private readonly items = new Map<string, TrackedDownload>();
  private readonly concurrency: number;
  private readonly maxAttempts: number;
  private readonly retryDelaysMs: number[];
  private readonly idlePollMs: number;
  private readonly pendingPollMs: number;
  private readonly progressIntervalMs: number;
  private readonly pendingLimit: number;
  private readonly reportDelayMs: number;
  private readonly doneRetentionMs: number;
  private readonly failedRetentionMs: number;
  private readonly maxItems: number;
  private readonly now: () => number;
  private readonly sleep: (ms: number, signal: AbortSignal) => Promise<void>;

  private timer: ReturnType<typeof setTimeout> | null = null;
  private reportTimer: ReturnType<typeof setTimeout> | null = null;
  private reportInFlight = false;
  private readonly reports = new Map<string, DownloadSyncReport>();
  private running = false;
  private paused = false;
  private pollInFlight = false;
  private lastPolledAt: number | null = null;
  private lastError: string | null = null;
  private disposed = false;
  private readonly lastProgressEmit = new Map<string, number>();

  constructor(private readonly options: DownloadCoordinatorOptions) {
    this.concurrency = clampConcurrency(options.concurrency);
    this.maxAttempts = Math.max(1, Math.trunc(options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS));
    this.retryDelaysMs =
      options.retryDelaysMs && options.retryDelaysMs.length > 0
        ? [...options.retryDelaysMs]
        : [...DEFAULT_RETRY_DELAYS];
    this.idlePollMs = Math.max(500, Math.trunc(options.idlePollMs ?? DEFAULT_IDLE_POLL_MS));
    this.pendingPollMs = Math.max(250, Math.trunc(options.pendingPollMs ?? DEFAULT_PENDING_POLL_MS));
    this.progressIntervalMs = Math.max(
      0,
      Math.trunc(options.progressIntervalMs ?? DEFAULT_PROGRESS_INTERVAL_MS),
    );
    this.pendingLimit = Math.max(1, Math.trunc(options.pendingLimit ?? DEFAULT_PENDING_LIMIT));
    this.reportDelayMs = Math.max(0, Math.trunc(options.reportDelayMs ?? 750));
    this.doneRetentionMs = Math.max(0, Math.trunc(options.doneRetentionMs ?? DEFAULT_DONE_RETENTION_MS));
    this.failedRetentionMs = Math.max(
      0,
      Math.trunc(options.failedRetentionMs ?? DEFAULT_FAILED_RETENTION_MS),
    );
    this.maxItems = Math.max(1, Math.trunc(options.maxItems ?? DEFAULT_MAX_ITEMS));
    this.now = options.now ?? Date.now;
    this.sleep = options.sleep ?? defaultSleep;
  }

  /* ---------------------------------------------------------------- */
  /* Lifecycle                                                         */
  /* ---------------------------------------------------------------- */

  start(): void {
    if (this.disposed || this.running) return;
    this.running = true;
    this.paused = false;
    this.emit("resumed");
    this.schedule(0);
  }

  /** Pause downloads and polling. Queued rows survive and resume on `start()`. */
  stop(): void {
    if (!this.running) return;
    this.running = false;
    this.paused = true;
    this.clearTimer();
    for (const tracked of this.items.values()) {
      if (tracked.info.state === "downloading" || tracked.info.state === "queued") {
        tracked.cancelReason = "pause";
        tracked.controller?.abort();
        tracked.sink?.abortSync();
        tracked.sink = null;
        tracked.info.state = "queued";
        tracked.info.receivedBytes = 0;
        tracked.info.percent = null;
        tracked.info.updatedAt = this.now();
      }
    }
    this.emit("paused");
  }

  /** the app is quitting: abort and delete partial files synchronously. */
  dispose(): void {
    this.disposed = true;
    this.running = false;
    this.clearTimer();
    if (this.reportTimer) {
      clearTimeout(this.reportTimer);
      this.reportTimer = null;
    }
    for (const tracked of this.items.values()) {
      tracked.controller?.abort();
      tracked.sink?.abortSync();
      tracked.sink = null;
      if (tracked.info.state === "downloading") {
        tracked.info.state = "cancelled";
        tracked.info.error = "The app closed before this download finished.";
        tracked.info.errorCode = "DOWNLOAD_INTERRUPTED";
        tracked.info.updatedAt = this.now();
      }
    }
  }

  get isRunning(): boolean {
    return this.running;
  }

  get isPaused(): boolean {
    return this.paused;
  }

  /* ---------------------------------------------------------------- */
  /* Snapshot                                                          */
  /* ---------------------------------------------------------------- */

  snapshot(): DownloadSnapshot {
    const root = this.resolveRoot();
    const items = [...this.items.values()].map((tracked) => ({ ...tracked.info }));
    return {
      items,
      running: this.running,
      paused: this.paused,
      active: items.filter((item) => item.state === "downloading").length,
      concurrency: this.concurrency,
      root: root.root,
      rootIsManaged: root.managed,
      lastPolledAt: this.lastPolledAt,
      lastError: this.lastError,
    };
  }

  item(key: string): DownloadItemInfo | null {
    const tracked = this.items.get(key);
    return tracked ? { ...tracked.info } : null;
  }

  /* ---------------------------------------------------------------- */
  /* Polling                                                           */
  /* ---------------------------------------------------------------- */

  /** Called when the shell opens the page; coalesced so it cannot spam. */
  requestPoll(): void {
    if (!this.running || this.pollInFlight) return;
    if (this.lastPolledAt !== null && this.now() - this.lastPolledAt < REQUEST_POLL_MIN_GAP_MS) return;
    this.schedule(0);
  }

  async pollNow(): Promise<void> {
    if (!this.running || this.pollInFlight || this.disposed) return;
    this.pollInFlight = true;
    try {
      const payload = await this.options.fetchPending(this.pendingLimit);
      if (this.disposed) return;
      this.reconcile(normalizePendingDownloads(payload));
      this.lastError = null;
    } catch (error) {
      if (this.disposed) return;
      this.lastError = error instanceof Error ? error.message : "Camxora could not be reached.";
      this.options.logger?.warn("download poll failed", { message: this.lastError });
    } finally {
      this.lastPolledAt = this.now();
      this.pollInFlight = false;
      if (!this.disposed) {
        this.pump();
        // A failed acknowledgement is retried on the next cycle.
        if (this.reports.size > 0) this.scheduleReportFlush();
        this.schedule(this.hasPendingWork() ? this.pendingPollMs : this.idlePollMs);
      }
    }
  }

  private schedule(delayMs: number): void {
    if (!this.running || this.disposed) return;
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.pollNow();
    }, Math.max(0, delayMs));
  }

  private clearTimer(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private hasPendingWork(): boolean {
    for (const tracked of this.items.values()) {
      if (tracked.info.state === "queued" || tracked.info.state === "downloading") return true;
    }
    return false;
  }

  /**
   * Merge one server payload into the tracked rows.
   *
   * A key (`task_id::role`) is downloaded at most once: a repeated pending item
   * never queues a second fetch, and a finished row is not re-downloaded even if
   * the server keeps reporting it.
   */
  private reconcile(pending: PendingDownloadItem[]): void {
    const root = this.resolveRoot();
    const allowLoopback = this.options.allowLoopbackHttp?.() === true;
    const seen = new Set<string>();

    for (const item of pending) {
      for (const role of ["primary", "secondary"] as DownloadTargetRole[]) {
        const target = role === "primary" ? item.primary : item.secondary;
        if (!target) continue;
        if (target.downloaded === true) continue;
        const key = targetKey(item.task_id, role);
        if (seen.has(key)) continue;
        seen.add(key);

        const url = target.download_url?.trim() ? target.download_url : null;
        const resolution = resolveDownloadTarget(
          {
            taskId: item.task_id,
            role,
            songId: item.song_id ?? null,
            batchId: item.batch_id ?? null,
            title: item.title ?? null,
            trackNumber: item.track_number ?? null,
            url,
            targetPath: target.target_path ?? null,
            outputDir: target.output_dir ?? null,
          },
          { root: root.root, allowLoopbackHttp: allowLoopback },
        );

        const existing = this.items.get(key);
        if (existing) {
          this.updateTracked(existing, item, url, resolution);
          continue;
        }

        const createdAt = this.now();
        const info: DownloadItemInfo = {
          key,
          taskId: item.task_id,
          songId: item.song_id ?? null,
          batchId: item.batch_id ?? null,
          title: item.title?.trim() || item.song_id || item.task_id,
          trackNumber: item.track_number ?? null,
          role,
          state: resolution.ok ? "queued" : "failed",
          hasUrl: Boolean(url),
          targetPath: resolution.ok ? resolution.target.path : null,
          receivedBytes: 0,
          totalBytes: null,
          percent: null,
          attempts: 0,
          error: resolution.ok ? null : resolution.message,
          errorCode: resolution.ok ? null : resolution.code,
          updatedAt: createdAt,
          completedAt: resolution.ok ? null : createdAt,
        };
        this.items.set(key, {
          info,
          url,
          createdAt,
          controller: null,
          sink: null,
          cancelReason: null,
        });
        this.emit(resolution.ok ? "queued" : "failed", key);
      }
    }

    for (const [key, tracked] of [...this.items]) {
      if (seen.has(key)) continue;
      if (tracked.info.state === "downloading" || tracked.info.state === "queued") continue;
      const stamp = tracked.info.completedAt ?? tracked.info.updatedAt;
      const retention =
        tracked.info.state === "done" ? this.doneRetentionMs : this.failedRetentionMs;
      if (this.now() - stamp >= retention) this.items.delete(key);
    }

    this.enforceItemCap();
  }

  private updateTracked(
    tracked: TrackedDownload,
    item: PendingDownloadItem,
    url: string | null,
    resolution: ReturnType<typeof resolveDownloadTarget>,
  ): void {
    const info = tracked.info;
    info.title = item.title?.trim() || item.song_id || item.task_id;
    info.songId = item.song_id ?? null;
    info.batchId = item.batch_id ?? null;
    info.trackNumber = item.track_number ?? null;
    info.hasUrl = Boolean(url);
    tracked.url = url;
    if (info.state === "downloading" || info.state === "done") return;

    if (resolution.ok) {
      // A failed row stays failed until the user retries; its path may refresh.
      info.targetPath = resolution.target.path;
      if (info.state === "queued") {
        info.error = null;
        info.errorCode = null;
      }
    } else if (info.state === "queued") {
      info.state = "failed";
      info.targetPath = null;
      info.error = resolution.message;
      info.errorCode = resolution.code;
      info.completedAt = this.now();
      info.updatedAt = this.now();
      this.emit("failed", info.key);
    }
  }

  private enforceItemCap(): void {
    if (this.items.size <= this.maxItems) return;
    const terminal = [...this.items.entries()]
      .filter(([, tracked]) => tracked.info.state !== "queued" && tracked.info.state !== "downloading")
      .sort((left, right) => left[1].createdAt - right[1].createdAt);
    while (this.items.size > this.maxItems && terminal.length > 0) {
      const next = terminal.shift();
      if (next) this.items.delete(next[0]);
    }
  }

  /* ---------------------------------------------------------------- */
  /* Scheduling                                                        */
  /* ---------------------------------------------------------------- */

  private pump(): void {
    if (!this.running || this.disposed) return;
    while (this.countActive() < this.concurrency) {
      const next = [...this.items.values()].find(
        (tracked) => tracked.info.state === "queued" && tracked.controller === null,
      );
      if (!next) return;
      void this.run(next);
    }
  }

  private countActive(): number {
    let active = 0;
    for (const tracked of this.items.values()) {
      if (tracked.info.state === "downloading") active += 1;
    }
    return active;
  }

  /* ---------------------------------------------------------------- */
  /* One item                                                          */
  /* ---------------------------------------------------------------- */

  private async run(tracked: TrackedDownload): Promise<void> {
    const info = tracked.info;
    const controller = new AbortController();
    tracked.controller = controller;
    tracked.cancelReason = null;
    info.state = "downloading";
    info.receivedBytes = 0;
    info.percent = null;
    info.attempts = 0;
    info.error = null;
    info.errorCode = null;
    info.completedAt = null;
    info.updatedAt = this.now();
    this.emit("started", info.key);

    try {
      for (;;) {
        info.attempts += 1;
        try {
          await this.downloadOnce(tracked, controller.signal);
          info.state = "done";
          info.error = null;
          info.errorCode = null;
          info.percent = info.totalBytes ? 100 : info.percent;
          info.completedAt = this.now();
          info.updatedAt = info.completedAt;
          this.options.logger?.info("download done", {
            key: info.key,
            bytes: info.receivedBytes,
            attempts: info.attempts,
          });
          this.queueReport(info);
          this.emit("done", info.key);
          return;
        } catch (error) {
          if (controller.signal.aborted) {
            await this.abortPartial(tracked);
            info.receivedBytes = 0;
            info.percent = null;
            if (tracked.cancelReason === "pause") {
              info.state = "queued";
              info.error = null;
              info.errorCode = null;
            } else {
              info.state = "cancelled";
              info.error = null;
              info.errorCode = null;
              info.completedAt = this.now();
            }
            info.updatedAt = this.now();
            this.emit(tracked.cancelReason === "pause" ? "paused" : "cancelled", info.key);
            return;
          }

          const failure = toDownloadError(error);
          const canRetry = failure.retryable && info.attempts < this.maxAttempts;
          if (!canRetry) {
            info.state = "failed";
            info.error = failure.message;
            info.errorCode = failure.code;
            info.completedAt = this.now();
            info.updatedAt = info.completedAt;
            this.options.logger?.warn("download failed", {
              key: info.key,
              code: failure.code,
              attempts: info.attempts,
            });
            this.emit("failed", info.key);
            return;
          }

          const delay = this.retryDelaysMs[Math.min(info.attempts - 1, this.retryDelaysMs.length - 1)];
          try {
            await this.sleep(delay, controller.signal);
          } catch {
            // The abort path handles the state on the next loop iteration.
            continue;
          }
          info.receivedBytes = 0;
          info.percent = null;
          info.updatedAt = this.now();
          this.emit("progress", info.key);
        }
      }
    } finally {
      tracked.controller = null;
      if (tracked.info.state !== "downloading") {
        tracked.info.updatedAt = this.now();
      }
      this.pump();
    }
  }

  private async downloadOnce(tracked: TrackedDownload, signal: AbortSignal): Promise<void> {
    const info = tracked.info;
    if (signal.aborted) throw abortError();
    if (!tracked.url) {
      throw new DownloadError("DOWNLOAD_URL_MISSING", DOWNLOAD_URL_MISSING_MESSAGE, false);
    }
    const targetPath = info.targetPath;
    if (!targetPath) {
      throw new DownloadError("DOWNLOAD_TARGET_OUTSIDE", "The target path is not usable.", false);
    }

    const existingSize = await this.options.io.fileSize(targetPath);
    if (existingSize !== null && existingSize > 0) {
      info.receivedBytes = existingSize;
      info.totalBytes = existingSize;
      info.percent = 100;
      return;
    }

    await this.ensureDir(path.dirname(targetPath));
    const response = await this.options.fetchDownload(tracked.url, signal);
    if (!response.ok) {
      throw httpDownloadError(response.status);
    }
    if (!response.body) {
      throw new DownloadError("DOWNLOAD_EMPTY", "The server returned an empty download.", true);
    }
    info.totalBytes = response.totalBytes;
    info.percent = percentOf(0, info.totalBytes);

    const sink = await this.createSink(targetPath);
    tracked.sink = sink;
    let received = 0;
    try {
      for await (const chunk of response.body) {
        if (signal.aborted) throw abortError();
        try {
          await sink.write(chunk);
        } catch (error) {
          throw new DownloadError(
            "DOWNLOAD_WRITE_FAILED",
            `The file could not be written: ${error instanceof Error ? error.message : String(error)}`,
            true,
          );
        }
        received += chunk.byteLength;
        info.receivedBytes = received;
        info.percent = percentOf(received, info.totalBytes);
        info.updatedAt = this.now();
        this.maybeEmitProgress(info.key);
      }
      if (signal.aborted) throw abortError();
      if (info.totalBytes !== null && received !== info.totalBytes) {
        throw new DownloadError(
          "DOWNLOAD_TRUNCATED",
          `The download stopped early (${received} of ${info.totalBytes} bytes).`,
          true,
        );
      }
      if (received === 0) {
        throw new DownloadError("DOWNLOAD_EMPTY", "The server returned an empty download.", true);
      }
      try {
        await sink.commit();
      } catch (error) {
        throw new DownloadError(
          "DOWNLOAD_WRITE_FAILED",
          `The file could not be saved: ${error instanceof Error ? error.message : String(error)}`,
          true,
        );
      }
      tracked.sink = null;
      info.receivedBytes = received;
      info.percent = percentOf(received, info.totalBytes);
    } catch (error) {
      await this.abortPartial(tracked);
      throw error;
    }
  }

  private async ensureDir(directory: string): Promise<void> {
    try {
      await this.options.io.ensureDir(directory);
    } catch (error) {
      throw new DownloadError(
        "DOWNLOAD_WRITE_FAILED",
        `The output folder could not be created: ${error instanceof Error ? error.message : String(error)}`,
        false,
      );
    }
  }

  private async createSink(targetPath: string): Promise<DownloadSink> {
    try {
      return await this.options.io.createSink(targetPath);
    } catch (error) {
      throw new DownloadError(
        "DOWNLOAD_WRITE_FAILED",
        `The file could not be written: ${error instanceof Error ? error.message : String(error)}`,
        false,
      );
    }
  }

  private async abortPartial(tracked: TrackedDownload): Promise<void> {
    const sink = tracked.sink;
    tracked.sink = null;
    if (!sink) return;
    try {
      await sink.abort();
    } catch {
      // Deleting a partial file must never mask the real error.
    }
  }

  private maybeEmitProgress(key: string): void {
    const stamp = this.now();
    const last = this.lastProgressEmit.get(key) ?? 0;
    if (stamp - last < this.progressIntervalMs) return;
    this.lastProgressEmit.set(key, stamp);
    this.emit("progress", key);
  }

  /* ---------------------------------------------------------------- */
  /* Completion reporting (1.7.1 parity)                               */
  /* ---------------------------------------------------------------- */

  private queueReport(info: DownloadItemInfo): void {
    if (!this.options.reportDownloads || !info.targetPath) return;
    this.reports.set(info.key, {
      taskId: info.taskId,
      role: info.role,
      outputDir: path.dirname(info.targetPath),
    });
    this.scheduleReportFlush();
  }

  private scheduleReportFlush(): void {
    if (!this.options.reportDownloads || this.reportTimer || this.disposed) return;
    this.reportTimer = setTimeout(() => {
      this.reportTimer = null;
      void this.flushReports();
    }, this.reportDelayMs);
  }

  private async flushReports(): Promise<void> {
    const reporter = this.options.reportDownloads;
    if (!reporter || this.reportInFlight || this.reports.size === 0) return;
    this.reportInFlight = true;
    const batch = [...this.reports.entries()];
    try {
      await reporter(batch.map(([, report]) => report));
      for (const [key] of batch) this.reports.delete(key);
    } catch (error) {
      // The files are safely on disk; the server is told on a later cycle.
      this.options.logger?.warn("download sync failed", {
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      this.reportInFlight = false;
    }
  }

  private resolveRoot(): DownloadRoot {
    return this.options.resolveRoot();
  }

  private emit(reason: DownloadChangedReason, key: string | null = null): void {
    try {
      this.options.emit?.({ reason, key });
    } catch {
      // A listener must never break the coordinator.
    }
  }

  /* ---------------------------------------------------------------- */
  /* Shell actions                                                     */
  /* ---------------------------------------------------------------- */

  retry(key: string): DownloadActionResult {
    const tracked = this.items.get(key);
    if (!tracked) {
      return {
        ok: false,
        error: { code: "DOWNLOAD_NOT_FOUND", message: "That download is no longer tracked." },
      };
    }
    if (tracked.info.state === "queued" || tracked.info.state === "downloading") {
      return {
        ok: false,
        error: { code: "DOWNLOAD_BUSY", message: "That download is already waiting or running." },
      };
    }
    if (tracked.info.state === "done") {
      return {
        ok: false,
        error: { code: "DOWNLOAD_DONE", message: "That song is already downloaded." },
      };
    }
    if (!tracked.url) {
      tracked.info.state = "failed";
      tracked.info.errorCode = "DOWNLOAD_URL_MISSING";
      tracked.info.error = DOWNLOAD_URL_MISSING_MESSAGE;
      tracked.info.updatedAt = this.now();
      this.emit("failed", key);
      return {
        ok: false,
        error: { code: "DOWNLOAD_URL_MISSING", message: DOWNLOAD_URL_MISSING_MESSAGE },
      };
    }
    tracked.info.state = "queued";
    tracked.info.attempts = 0;
    tracked.info.receivedBytes = 0;
    tracked.info.percent = null;
    tracked.info.error = null;
    tracked.info.errorCode = null;
    tracked.info.completedAt = null;
    tracked.info.updatedAt = this.now();
    this.emit("retried", key);
    if (this.running) this.pump();
    return { ok: true };
  }

  cancel(key: string): DownloadActionResult {
    const tracked = this.items.get(key);
    if (!tracked) {
      return {
        ok: false,
        error: { code: "DOWNLOAD_NOT_FOUND", message: "That download is no longer tracked." },
      };
    }
    if (tracked.info.state === "done") {
      return {
        ok: false,
        error: { code: "DOWNLOAD_DONE", message: "That song is already downloaded." },
      };
    }
    if (tracked.info.state === "cancelled") return { ok: true };

    tracked.cancelReason = "user";
    tracked.info.state = "cancelled";
    tracked.info.error = null;
    tracked.info.errorCode = null;
    tracked.info.completedAt = this.now();
    tracked.info.updatedAt = tracked.info.completedAt;
    tracked.info.percent = null;
    tracked.info.receivedBytes = 0;
    tracked.controller?.abort();
    tracked.sink?.abortSync();
    tracked.sink = null;
    this.emit("cancelled", key);
    return { ok: true };
  }
}

function toDownloadError(error: unknown): DownloadError {
  if (error instanceof DownloadError) return error;
  if (error instanceof Error && error.name === "AbortError") {
    return new DownloadError("DOWNLOAD_CANCELLED", "The download was cancelled.", false);
  }
  return new DownloadError(
    "DOWNLOAD_NETWORK_ERROR",
    "The download could not be completed. Check your connection.",
    true,
  );
}

function httpDownloadError(status: number): DownloadError {
  if (status === 404 || status === 410) {
    return new DownloadError("DOWNLOAD_URL_GONE", DOWNLOAD_URL_GONE_MESSAGE, false);
  }
  if (status === 401 || status === 403) {
    return new DownloadError("DOWNLOAD_URL_FORBIDDEN", DOWNLOAD_URL_FORBIDDEN_MESSAGE, false);
  }
  if (status === 429 || status >= 500 || status === 0) {
    return new DownloadError(
      `DOWNLOAD_HTTP_${status}`,
      `The download server did not respond (HTTP ${status || "network error"}).`,
      true,
    );
  }
  return new DownloadError(
    "DOWNLOAD_TARGET_REJECTED",
    `The download was rejected (HTTP ${status}).`,
    false,
  );
}
