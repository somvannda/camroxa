/**
 * Background auto-video coordinator.
 *
 * Polls the platform while the app is signed in and starts local Vizzy renders
 * when a Progress row becomes ready:
 *   audio downloads complete + branch background exists + profile template.
 *
 * Rendering itself stays in the offscreen host; this only decides *what* to
 * enqueue. It is independent of the page the user is on, so a batch finishes
 * even when the Music/Progress view is closed.
 *
 * Long and reel use separate pipeline batch ids, so a merge can never combine a
 * 16:9 and a 9:16 render.
 */
import fs from "node:fs";
import path from "node:path";
import { logger } from "./logger";
import { apiRequest, apiRequestBytes } from "./api-client";
import { isPathInside } from "./media-utils";
import { getDevicePreferences } from "./device-settings";
import { sessionStore } from "./session";
import { listQueue } from "./pipeline-queue";
import { enqueuePipelineRequest } from "./pipeline-enqueue";
import { listVideoTemplates } from "./video-templates";
import {
  selectAutoVideoCandidate,
  type AutoVideoBranch,
  type AutoVideoHistoryBatch,
  type AutoVideoProfile,
  type AutoVideoProgressRow,
  type AutoVideoSwitches,
} from "./auto-video";
import type { Store } from "./database";
import type {
  PipelineAutoStatus,
  PipelineBranch,
} from "../shared/types";

const DEFAULT_INTERVAL_MS = 12_000;
const DEFAULT_CACHE_MS = 15_000;

export interface AutoVideoCoordinatorDeps {
  store: Store;
  templatesRoot: string;
  isRunnerRunning: () => boolean;
  startRunner: () => void;
  onChanged?: () => void;
  /** Test hook; defaults to the real authenticated API client. */
  request?: typeof apiRequest;
  /** Test hook; the real coordinator only polls while signed in. */
  hasSession?: () => boolean;
  /** Test hook; defaults to the device's configured Suno output folder. */
  getSunoOutputDir?: () => string;
  intervalMs?: number;
  cacheMs?: number;
  log?: (level: "info" | "warn" | "error", message: string, detail?: unknown) => void;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  const record = asRecord(value);
  for (const key of ["profiles", "rows", "batches", "items", "results"]) {
    if (Array.isArray(record[key])) return record[key] as T[];
  }
  return [];
}

function readBoolean(value: unknown): boolean {
  if (value === true) return true;
  if (value === false || value === null || value === undefined) return false;
  if (typeof value === "number") return value !== 0;
  const text = String(value).trim().toLowerCase();
  return text === "true" || text === "1" || text === "on" || text === "yes";
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

interface Cache<T> {
  at: number;
  value: T;
}

export class AutoVideoCoordinator {
  private timer: NodeJS.Timeout | null = null;
  private running = false;
  private polling = false;
  private profilesCache: Cache<AutoVideoProfile[]> | null = null;
  private templatesCache:
    | Cache<Array<{ id: string; kind: AutoVideoBranch }>>
    | null = null;
  private lastError = "";
  private lastSkip = "";
  private current: PipelineAutoStatus = {
    running: false,
    state: "stopped",
    message: "stopped.",
    lastPollAt: null,
  };

  constructor(private readonly deps: AutoVideoCoordinatorDeps) {}

  status(): PipelineAutoStatus {
    return { ...this.current };
  }

  start(options: { immediate?: boolean } = {}): void {
    if (this.running) return;
    this.running = true;
    this.setStatus("idle", "Watching for a run with MP3s, a background and a saved template.");
    const interval = this.deps.intervalMs ?? DEFAULT_INTERVAL_MS;
    this.timer = setInterval(() => void this.tick(), interval);
    this.timer.unref?.();
    if (options.immediate !== false) void this.tick();
    this.log("info", "auto-video coordinator started", { interval });
  }

  stop(): void {
    if (!this.running) return;
    this.running = false;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.setStatus("stopped", "stopped.");
    this.log("info", "auto-video coordinator stopped");
  }

  isRunning(): boolean {
    return this.running;
  }

  /** One poll. Public so a future manual kick/retry can reuse the same rules. */
  async tick(): Promise<void> {
    if (!this.running || this.polling) return;
    this.touchPoll();
    if (!this.hasSession()) {
      this.setStatus("idle", "Sign in to auto-render videos.");
      return;
    }
    if (this.deps.isRunnerRunning()) {
      this.setStatus("rendering", "Rendering queued videos.");
      return;
    }

    const queued = listQueue(this.deps.store).some(
      (job) =>
        job.status === "queued" ||
        job.status === "rendering" ||
        job.status === "encoding" ||
        job.status === "merging",
    );
    if (queued) {
      // Resume a durable queue left behind by a restart.
      this.setStatus("rendering", "Resuming queued videos.");
      this.deps.startRunner();
      return;
    }

    this.polling = true;
    try {
      const settings = await this.settings();
      if (!settings.long && !settings.reel) {
        this.setStatus("idle", "Video (16:9) and Video (9:16) are both off.");
        return;
      }

      const [progress, history, profiles, templates] = await Promise.all([
        this.request({ method: "GET", path: "/progress", query: { limit: 100 } }),
        this.request({ method: "GET", path: "/music/history", query: { limit: 100 } }),
        this.profiles(),
        this.templates(),
      ]);

      const rawRows = asArray<AutoVideoProgressRow>(progress.data).filter(
        (row) => row && typeof row === "object" && row.meta && typeof row.meta === "object",
      );
      // A relative run key is relative to the device's Suno output folder, not
      // the app's working directory; resolve it before the render queue sees it.
      const sunoRoot = this.sunoOutputDir();
      const rows =
        sunoRoot === ""
          ? rawRows
          : rawRows.map((row) => {
              const runDir = clean(row.meta.run_dir);
              if (!runDir || path.isAbsolute(runDir)) return row;
              return { ...row, meta: { ...row.meta, run_dir: path.resolve(sunoRoot, runDir) } };
            });
      const batches = asArray<AutoVideoHistoryBatch>(history.data);
      if (rows.length === 0 || batches.length === 0) {
        this.setStatus("waiting", "Waiting for a batch with finished downloads.");
        return;
      }
      // Only continue the newest generation. Older unfinished batches are left
      // alone; the Python app never auto-restarts a previous day's run.
      const latestRunDate = rows
        .map((row) => clean(row.run_date))
        .filter(Boolean)
        .sort()
        .at(-1);
      const activeRows = latestRunDate
        ? rows.filter((row) => !clean(row.run_date) || clean(row.run_date) === latestRunDate)
        : rows;

      // A missing run background blocks the plan; cache the generated images
      // here instead of waiting for the Image page to be opened.
      await this.syncRunImages(activeRows, settings).catch(() => 0);

      const candidate = selectAutoVideoCandidate({
        settings,
        rows: activeRows,
        batches,
        profiles,
        templates,
        localJobs: listQueue(this.deps.store),
        resolveBackground: (row, branch) => this.resolveBackground(row, branch),
      });
      if (!candidate) {
        this.lastSkip = "";
        this.setStatus(
          "waiting",
          "Waiting for finished MP3s, a 16:9/9:16 background and the saved template.",
        );
        return;
      }

      const outputDir =
        sunoRoot && !path.isAbsolute(candidate.outputDir)
          ? path.resolve(sunoRoot, candidate.outputDir)
          : candidate.outputDir;
      const result = enqueuePipelineRequest({
        store: this.deps.store,
        templatesRoot: this.deps.templatesRoot,
        request: {
          batchId: candidate.pipelineBatchId,
          outputDir,
          merge: candidate.merge,
          mergeName: candidate.mergeName,
          jobs: candidate.jobs.map((job) => ({
            ...job,
            audioDir: path.isAbsolute(job.audioDir)
              ? job.audioDir
              : path.resolve(sunoRoot || outputDir, job.audioDir),
          })),
        },
      });

      if (result.created > 0) {
        this.lastSkip = "";
        this.log("info", "auto-video enqueued", {
          batchId: candidate.pipelineBatchId,
          branch: candidate.branch,
          renders: result.created,
          templateId: candidate.templateId,
        });
        this.setStatus(
          "queued",
          `Queued ${result.created} ${candidate.branch === "reel" ? "reel" : "16:9"} render${
            result.created === 1 ? "" : "s"
          }.`,
          { batchId: candidate.pipelineBatchId, branch: candidate.branch },
        );
        this.deps.onChanged?.();
        this.deps.startRunner();
        return;
      }

      const reason = result.message ?? "Nothing was queued.";
      this.setStatus("waiting", reason);
      if (reason !== this.lastSkip) {
        this.lastSkip = reason;
        this.log("warn", "auto-video skipped a ready row", {
          batchId: candidate.pipelineBatchId,
          branch: candidate.branch,
          reason,
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.setStatus("error", message);
      if (message !== this.lastError) {
        this.lastError = message;
        this.log("warn", "auto-video poll failed", { error: message });
      }
    } finally {
      this.polling = false;
    }
  }

  /* ------------------------------------------------------------------ */

  private sunoOutputDir(): string {
    try {
      const configured = this.deps.getSunoOutputDir?.() ?? getDevicePreferences(this.deps.store).sunoOutputDir;
      return clean(configured);
    } catch {
      return "";
    }
  }

  private async settings(): Promise<AutoVideoSwitches> {
    // Read every tick: the user can check/uncheck Video at any moment.
    const response = await this.request({ method: "GET", path: "/settings" });
    const data = asRecord(response.data);
    return {
      long: readBoolean(data.autoVideoAfterSuno),
      reel: readBoolean(data.autoReelAfterVideo),
      merge: readBoolean(data.autoMergeAfterVideo),
    };
  }

  private async profiles(): Promise<AutoVideoProfile[]> {
    if (this.fresh(this.profilesCache)) return this.profilesCache.value;
    const response = await this.request({ method: "GET", path: "/profiles" });
    const value = asArray<AutoVideoProfile>(response.data).filter(
      (profile) => profile && clean(profile.id),
    );
    this.profilesCache = { at: Date.now(), value };
    return value;
  }

  private async templates(): Promise<Array<{ id: string; kind: AutoVideoBranch }>> {
    if (this.fresh(this.templatesCache)) return this.templatesCache.value;
    const value = listVideoTemplates(this.deps.templatesRoot).map((template) => ({
      id: template.id,
      kind: template.kind,
    }));
    this.templatesCache = { at: Date.now(), value };
    return value;
  }

  private fresh<T>(cache: Cache<T> | null): cache is Cache<T> {
    if (!cache) return false;
    const ttl = this.deps.cacheMs ?? DEFAULT_CACHE_MS;
    return Date.now() - cache.at < ttl;
  }

  private get request(): typeof apiRequest {
    return this.deps.request ?? apiRequest;
  }

  private setStatus(
    state: PipelineAutoStatus["state"],
    message: string,
    extra: { batchId?: string; branch?: PipelineBranch } = {},
  ): void {
    this.current = {
      running: this.running,
      state,
      message,
      lastPollAt: this.current.lastPollAt,
      ...extra,
    };
  }

  private touchPoll(): void {
    this.current = { ...this.current, running: this.running, lastPollAt: Date.now() };
  }

  private hasSession(): boolean {
    if (this.deps.hasSession) return this.deps.hasSession();
    return Boolean(sessionStore.load()?.accessToken);
  }

  /** Prefer the API/run-folder path, then the known local filenames. */
  private resolveBackground(
    row: AutoVideoProgressRow,
    branch: AutoVideoBranch,
  ): string | null {
    const meta = row.meta;
    const runDir = clean(meta.run_dir);
    const stored = clean(
      branch === "long" ? meta.background_16x9_path : meta.background_9x16_path,
    );
    const absolute = (value: string): string | null => {
      if (!value) return null;
      const resolved = path.isAbsolute(value)
        ? value
        : path.resolve(runDir || ".", value);
      try {
        return fs.statSync(resolved).isFile() ? resolved : null;
      } catch {
        return null;
      }
    };

    const fromMeta = absolute(stored);
    if (fromMeta) return fromMeta;
    if (!runDir) return null;

    const stem = branch === "long" ? "background-16x9" : "background-9x16";
    const altStem = branch === "long" ? "background_16x9" : "background_9x16";
    for (const name of [
      `${stem}.png`,
      `${stem}.jpg`,
      `${stem}.jpeg`,
      `${stem}.webp`,
      `${altStem}.png`,
      `${altStem}.jpg`,
      `${altStem}.jpeg`,
      `${altStem}.webp`,
    ]) {
      const found = absolute(path.join(runDir, name));
      if (found) return found;
    }
    return null;
  }

  private lastImageSyncAt = 0;

  /**
   * Download the run's generated images into the run folder.
   *
   * Image outputs live on the server until something reads them; the Image page
   * caches them only while its previews are mounted, so a batch could sit for
   * hours until the user happened to open that page. The coordinator needs the
   * 16:9/9:16 background to plan a render, so it caches the missing images
   * itself (backgrounds and thumbnails) before selecting a candidate.
   */
  private async syncRunImages(
    rows: AutoVideoProgressRow[],
    settings: AutoVideoSwitches,
  ): Promise<number> {
    const now = Date.now();
    if (now - this.lastImageSyncAt < 60_000) return 0;
    this.lastImageSyncAt = now;

    const root = this.sunoOutputDir();
    if (!root) return 0;

    const wanted = new Map<string, string>();
    const remember = (value: string, runDir: string): void => {
      const text = clean(value);
      if (!text) return;
      const absolute = path.isAbsolute(text) ? text : path.resolve(runDir, text);
      if (!isPathInside(root, absolute)) return;
      wanted.set(absolute.toLowerCase(), absolute);
    };
    const branches: AutoVideoBranch[] = [];
    if (settings.long) branches.push("long");
    if (settings.reel) branches.push("reel");

    for (const row of rows) {
      const runDir = clean(row.meta.run_dir);
      if (!runDir) continue;
      for (const branch of branches) {
        remember(
          (branch === "long" ? row.meta.background_16x9_path : row.meta.background_9x16_path) ??
            "",
          runDir,
        );
        const stems =
          branch === "long"
            ? ["background-16x9", "background_16x9", "thumbnail-16x9", "thumbnail_16x9"]
            : ["background-9x16", "background_9x16", "thumbnail-9x16", "thumbnail_9x16"];
        for (const stem of stems) {
          for (const extension of ["png", "jpg", "jpeg", "webp"]) {
            remember(path.join(runDir, `${stem}.${extension}`), runDir);
          }
        }
      }
    }

    const missing = [...wanted.values()].filter((absolute) => !fs.existsSync(absolute));
    if (missing.length === 0) return 0;

    let items: Array<Record<string, unknown>>;
    try {
      const response = await this.request({
        method: "GET",
        path: "/image-jobs",
        query: { limit: 200 },
      });
      items = asArray<Record<string, unknown>>(asRecord(response.data).items);
    } catch {
      return 0;
    }

    let written = 0;
    for (const job of items) {
      const status = String(job.status ?? "").toLowerCase();
      if (status !== "success" && status !== "completed") continue;
      const target = clean(
        typeof job.output_image_path === "string" ? job.output_image_path : "",
      );
      if (!target) continue;
      const absolute = path.isAbsolute(target) ? target : path.resolve(root, target);
      const desired = wanted.get(absolute.toLowerCase());
      if (!desired || fs.existsSync(desired)) continue;
      const jobId = clean(typeof job.id === "string" ? job.id : "");
      if (!jobId) continue;
      try {
        const bytes = await apiRequestBytes({
          method: "GET",
          path: `/image-jobs/${encodeURIComponent(jobId)}/output`,
        });
        if (!bytes.bytes.byteLength) continue;
        fs.mkdirSync(path.dirname(desired), { recursive: true });
        fs.writeFileSync(desired, Buffer.from(bytes.bytes));
        written += 1;
      } catch {
        // A failed fetch is retried on a later tick.
      }
    }
    if (written > 0) this.log("info", "image assets cached", { written });
    return written;
  }

  private log(
    level: "info" | "warn" | "error",
    message: string,
    detail?: unknown,
  ): void {
    if (this.deps.log) {
      this.deps.log(level, message, detail);
      return;
    }
    logger[level](message, detail);
  }
}
