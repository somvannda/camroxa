import { EventEmitter } from "node:events";
import { randomUUID } from "node:crypto";
import path from "node:path";
import type { JobEvent, JobPayload, JobStatus, JobType } from "../shared/app-types";
import { mergeAudioByVersion } from "./ffmpegMerge";
import { generateSongDraftWithDeepSeek } from "./ai/deepseekSong";
import { generateSongDraftWithSlai } from "./ai/slaiSong";
import { pickBatchAndMark, type DbCfg } from "./db/phrasePools";
import { getRecentForUniqueness, insertHistory, upsertSong, listSongsByBatchId } from "./db/songStore";
import { buildSunoOutputPaths, downloadToFile, hashSunoGenerateRequest, sunoApiGenerate, sunoApiTryGetTracks, type SunoApiModel } from "./suno/sunoApi";
import { getSunoTaskByRequestHash, upsertSunoTask } from "./db/sunoTaskStore";
import { SunoSubmitter } from "./suno/sunoSubmitter";

type PoolBuffer = {
  openings: Array<{ line1: string; line2: string }>;
  titles: string[];
  albums: string[];
};

const poolBuffers = new Map<string, PoolBuffer>();
const recentTitlePrefixesByDb = new Map<string, string[]>();

const batchAlbumByBatchId = new Map<string, { album: string; createdAtMs: number }>();

const recentAvoidCache = new Map<
  string,
  { titles: string[]; albums: string[]; openings: string[]; createdAtMs: number }
>();

function poolKey(db: DbCfg) {
  return `${db.user}@${db.host}:${db.port}/${db.database}`;
}

async function getPooled(db: DbCfg, opts: { opening: boolean; title: boolean; album: boolean }) {
  const key = poolKey(db);
  const buf = poolBuffers.get(key) ?? { openings: [], titles: [], albums: [] };
  const needOpenings = opts.opening && buf.openings.length === 0;
  const needTitles = opts.title && buf.titles.length === 0;
  const needAlbums = opts.album && buf.albums.length === 0;

  if (needOpenings || needTitles || needAlbums) {
    const batch = await pickBatchAndMark(db, { opening: needOpenings, title: needTitles, album: needAlbums, n: 40 });
    if (batch.openings.length) buf.openings.push(...batch.openings.map((o) => ({ line1: o.line1, line2: o.line2 })));
    if (batch.titles.length) buf.titles.push(...batch.titles.map((t) => t.title));
    if (batch.albums.length) buf.albums.push(...batch.albums.map((a) => a.album));
    poolBuffers.set(key, buf);
  }

  return {
    opening: opts.opening ? buf.openings.shift() : undefined,
    title: opts.title ? pickNextTitle(key, buf) : undefined,
    album: opts.album ? buf.albums.shift() : undefined,
  };
}

function cleanupBatchAlbums() {
  const cutoff = Date.now() - 6 * 60 * 60 * 1000;
  for (const [k, v] of batchAlbumByBatchId) {
    if (v.createdAtMs < cutoff) batchAlbumByBatchId.delete(k);
  }
}

function normalize(s: string) {
  return String(s || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function firstWord(text: string) {
  const t = normalize(text);
  if (!t) return "";
  return t.split(" ")[0] ?? "";
}

function pickNextTitle(dbKey: string, buf: PoolBuffer) {
  if (!buf.titles.length) return undefined;
  const recent = recentTitlePrefixesByDb.get(dbKey) ?? [];
  const avoid = new Set(recent);
  const preferNot = new Set(["i", "we", "don't", "dont"]);

  function takeAt(idx: number) {
    const [picked] = buf.titles.splice(idx, 1);
    const prefix = firstWord(picked);
    if (prefix) {
      const next = [...recent, prefix].slice(-3);
      recentTitlePrefixesByDb.set(dbKey, next);
    }
    return picked;
  }

  const idxPreferred = buf.titles.findIndex((t) => {
    const p = firstWord(t);
    return p && !avoid.has(p) && !preferNot.has(p);
  });
  if (idxPreferred >= 0) return takeAt(idxPreferred);

  const idxAvoidOnly = buf.titles.findIndex((t) => {
    const p = firstWord(t);
    return p && !avoid.has(p);
  });
  if (idxAvoidOnly >= 0) return takeAt(idxAvoidOnly);

  return takeAt(0);
}

function opening2(lyrics: string) {
  const lines = String(lyrics || "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 2);
  return lines.join("\n");
}

function cleanupAvoidCache() {
  const cutoff = Date.now() - 10 * 60 * 1000;
  for (const [k, v] of recentAvoidCache) {
    if (v.createdAtMs < cutoff) recentAvoidCache.delete(k);
  }
}

async function getAvoidLists(db: DbCfg, historyWindow: number) {
  cleanupAvoidCache();
  const key = `${poolKey(db)}|h=${historyWindow}`;
  const cached = recentAvoidCache.get(key);
  if (cached) return cached;

  const recent = await getRecentForUniqueness(db, historyWindow);
  const titleSet = new Set<string>();
  const albumSet = new Set<string>();
  const openingSet = new Set<string>();
  for (const s of recent) {
    const t = normalize(s.title);
    const a = normalize(s.album);
    const o = normalize(opening2(s.lyricsPolished || s.lyricsRaw));
    if (t) titleSet.add(t);
    if (a) albumSet.add(a);
    if (o) openingSet.add(o);
  }
  const titles = Array.from(titleSet).slice(0, 120);
  const albums = Array.from(albumSet).slice(0, 120);
  const openings = Array.from(openingSet).slice(0, 120);
  const out = { titles, albums, openings, createdAtMs: Date.now() };
  recentAvoidCache.set(key, out);
  return out;
}

type JobItem = {
  jobId: string;
  payload: JobPayload;
  cancelled: boolean;
};

export type JobQueueEvents = {
  event: (event: JobEvent) => void;
};

function nowIso() {
  return new Date().toISOString();
}

function emitEvent(emitter: EventEmitter, event: Omit<JobEvent, "createdAt">) {
  emitter.emit("event", { ...event, createdAt: nowIso() } satisfies JobEvent);
}

async function sleep(ms: number) {
  await new Promise((r) => setTimeout(r, ms));
}

export class JobQueue {
  private emitter = new EventEmitter();
  private queue: JobItem[] = [];
  private running = false;
  private current: JobItem | null = null;
  private sunoSubmitter = new SunoSubmitter({
    maxConcurrent: 5,
    onEvent: (e) =>
      emitEvent(this.emitter, {
        jobId: e.jobId,
        jobType: "suno",
        status: e.status,
        message: e.message,
        progress: e.progress,
      }),
  });

  onEvent(listener: (event: JobEvent) => void) {
    this.emitter.on("event", listener);
    return () => this.emitter.off("event", listener);
  }

  enqueue(payload: JobPayload) {
    const jobId = randomUUID();
    const job: JobItem = { jobId, payload, cancelled: false };
    this.queue.push(job);
    emitEvent(this.emitter, {
      jobId,
      jobType: payload.jobType,
      status: "queued",
      message: `${payload.jobType} queued`,
    });
    void this.run();
    return { jobId };
  }

  cancel(jobId: string) {
    if (this.current?.jobId === jobId) {
      this.current.cancelled = true;
      emitEvent(this.emitter, {
        jobId,
        jobType: this.current.payload.jobType,
        status: "cancelled",
        message: "cancel requested",
      });
      return { ok: true };
    }

    const idx = this.queue.findIndex((x) => x.jobId === jobId);
    if (idx >= 0) {
      const [removed] = this.queue.splice(idx, 1);
      emitEvent(this.emitter, {
        jobId,
        jobType: removed.payload.jobType,
        status: "cancelled",
        message: "cancelled",
      });
      return { ok: true };
    }

    return { ok: false };
  }

  getState() {
    return {
      running: this.running,
      currentJobId: this.current?.jobId ?? null,
      queuedCount: this.queue.length,
    };
  }

  private async run() {
    if (this.running) return;
    this.running = true;
    try {
      while (this.queue.length) {
        const job = this.queue.shift();
        if (!job) break;
        this.current = job;
        await this.process(job);
        this.current = null;
      }
    } finally {
      this.running = false;
      this.current = null;
    }
  }

  private async process(job: JobItem) {
    const jobType: JobType = job.payload.jobType;
    const action = job.payload.jobType === "workflow" ? job.payload.action : undefined;
    const versionType = job.payload.jobType === "merge" ? job.payload.versionType : undefined;
    let song: JobEvent["song"] | undefined;
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType,
      status: "running",
      message: `${jobType} started`,
      progress: 0,
      action,
      versionType,
    });

    try {
      if (jobType === "workflow") {
        const action = job.payload.jobType === "workflow" ? job.payload.action : "run";
        if (action === "generate") song = await this.runGenerate(job);
        else await this.runMockWorkflow(job);
      } else if (jobType === "merge") {
        await this.runMerge(job);
      } else {
        await this.runSuno(job);
      }

      if (job.cancelled) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType,
          status: "cancelled",
          message: "cancelled",
          action,
          versionType,
        });
        return;
      }

      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType,
        status: "completed",
        message: action ? `${action} completed` : `${jobType} completed`,
        progress: 100,
        action,
        versionType,
        song,
      });
    } catch (e) {
      if (e instanceof Error) {
        console.error(`[jobQueue] job failed ${job.jobId} (${jobType})`, e.stack || e.message);
      } else {
        console.error(`[jobQueue] job failed ${job.jobId} (${jobType})`, e);
      }
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType,
        status: "failed",
        message: e instanceof Error ? e.message : "job failed",
        action,
        versionType,
      });
    }
  }

  private async runMockWorkflow(job: JobItem) {
    const action = job.payload.jobType === "workflow" ? job.payload.action : "run";
    const steps = [
      { p: 10, m: `${action}: preparing` },
      { p: 35, m: `${action}: generating` },
      { p: 65, m: `${action}: processing` },
      { p: 90, m: `${action}: finalizing` },
    ];

    for (const s of steps) {
      if (job.cancelled) return;
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "workflow",
        status: "running" as JobStatus,
        message: s.m,
        progress: s.p,
        action,
      });
      await sleep(450);
    }
  }

  private async runMerge(job: JobItem) {
    if (job.payload.jobType !== "merge") return;
    const { versionType, chunkSize, inputDir, outputDir, ffmpegPath } = job.payload;
    if (!ffmpegPath || !ffmpegPath.trim()) throw new Error("FFmpeg path is not configured");

    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `scanning ${inputDir}`,
      progress: 5,
      versionType,
    });

    const result = await mergeAudioByVersion({
      ffmpegPath,
      inputDir,
      outputDir,
      versionType,
      chunkSize,
    });

    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `inputs OK=${result.inputCounts.OK} ALT=${result.inputCounts.ALT}`,
      progress: 25,
      versionType,
    });

    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `created ${result.outputFiles.length} merged files`,
      progress: 90,
      versionType,
    });
  }

  private async runSuno(job: JobItem) {
    if (job.payload.jobType !== "suno") return;
    const { batchId, expectedCount } = job.payload;
    let effectiveExpectedCount = expectedCount;
    const db = job.payload.db;
    if (!db) throw new Error("Postgres is not configured for Suno automation");

    const retryCount = Math.max(1, job.payload.sunoRetryCount ?? 3);
    const apiKey = String(job.payload.sunoApiKey || "").trim();
    if (!apiKey) throw new Error("Suno API key is not configured");

    let songs = (job.payload.songs ?? []).filter(Boolean);
    if (!songs.length) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `waiting for ${expectedCount} generated songs in batch ${batchId}`,
        progress: 5,
      });

      const waitForSongsTimeoutMs = Math.max(15 * 60_000, expectedCount * 2 * 60_000);
      const start = Date.now();
      songs = await listSongsByBatchId(db, batchId);
      while (!job.cancelled && songs.length < expectedCount && Date.now() - start < waitForSongsTimeoutMs) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType: "suno",
          status: "running",
          message: `songs ready: ${songs.length}/${expectedCount}`,
          progress: Math.min(20, Math.floor((20 * songs.length) / Math.max(1, expectedCount))),
        });
        await sleep(2000);
        songs = await listSongsByBatchId(db, batchId);
      }

      if (job.cancelled) return;
      if (songs.length < expectedCount) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType: "suno",
          status: "running",
          message: `Timed out waiting for songs: ${songs.length}/${expectedCount} (continuing with ${songs.length})`,
          progress: 20,
        });
        effectiveExpectedCount = songs.length;
      }
    }

    const outputDirOk = String(job.payload.sunoOutputDirOk || job.payload.sunoOutputDir || job.payload.downloadsDir || "").trim();
    if (!outputDirOk) throw new Error("Suno output directory is not configured");
    const outputDirAlt = String(job.payload.sunoOutputDirAlt || outputDirOk).trim() || outputDirOk;

    const version = job.payload.version ?? "v5.5";
    const model: SunoApiModel = version === "v5" ? "V5" : "V5_5";
    const callbackUrl = String(job.payload.sunoCallbackUrl || "").trim() || "https://api.example.com/callback";
    let deferred = 0;

    const runSongs = songs.slice(0, effectiveExpectedCount);
    for (let i = 0; i < runSongs.length; i += 1) {
      if (job.cancelled) return;
      const song = runSongs[i]!;
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `Suno API: generating ${i + 1}/${runSongs.length} (${song.title})`,
        progress: 20 + Math.floor((60 * i) / Math.max(1, runSongs.length)),
      });

      let lastErr: unknown;
      for (let attempt = 0; attempt < retryCount; attempt += 1) {
        try {
          const prompt = song.lyricsPolished || song.lyricsRaw;
          const requestHash = hashSunoGenerateRequest({
            model,
            title: song.title,
            prompt,
            style: song.songDescription,
            instrumental: false,
          });

          const cached = await getSunoTaskByRequestHash(db, requestHash);
          let taskId = cached?.taskId || "";

          if (cached?.audioUrlOk && cached.audioUrlAlt) {
            emitEvent(this.emitter, {
              jobId: job.jobId,
              jobType: "suno",
              status: "running",
              message: `Suno API: using cached result (${i + 1}/${runSongs.length})`,
              progress: 45 + Math.floor((30 * i) / Math.max(1, runSongs.length)),
            });
            const trackNo = typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : i + 1;
            const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: song.title, trackNo });
            const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: song.title, trackNo });
            await downloadToFile(cached.audioUrlOk, pathsOk.ok);
            await downloadToFile(cached.audioUrlAlt, pathsAlt.alt);
            break;
          }

          if (!taskId) {
            const gen = await sunoApiGenerate({
              apiKey,
              model,
              title: song.title,
              lyrics: prompt,
              style: song.songDescription,
              instrumental: false,
              callbackUrl,
            });
            taskId = gen.taskId;
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: "PENDING",
              outputDirOk,
              outputDirAlt,
            });
          }

          const r = await sunoApiTryGetTracks(apiKey, taskId);
          if (r.audioUrls.length >= 2) {
            const okUrl = String(r.audioUrls[0] || "").trim();
            const altUrl = String(r.audioUrls[1] || "").trim();
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: String(r.status || "SUCCESS"),
              audioUrlOk: okUrl,
              audioUrlAlt: altUrl,
              outputDirOk,
              outputDirAlt,
            });

            const trackNo = typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : i + 1;
            const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: song.title, trackNo });
            const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: song.title, trackNo });
            await downloadToFile(okUrl, pathsOk.ok);
            await downloadToFile(altUrl, pathsAlt.alt);
          } else {
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: String(r.status || "PENDING"),
              outputDirOk,
              outputDirAlt,
            });
            deferred += 1;
          }
          break;
        } catch (e) {
          lastErr = e;
          await sleep(1500 * (attempt + 1));
        }
      }
      if (lastErr) {
        const msg = lastErr instanceof Error ? lastErr.message : "Suno API generation failed";
        throw new Error(msg);
      }
    }

    if (deferred > 0) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `Suno API: ${deferred} task(s) processing; will auto-download in background`,
        progress: 98,
      });
    }

    if (job.payload.mergeEnabled && deferred === 0) {
      const mergedOkDir = path.join(outputDirOk, "merge");
      const mergedAltDir = path.join(outputDirAlt, "merge");
      const ffmpegPath = String(job.payload.ffmpegPath || "").trim();
      if (!ffmpegPath) throw new Error("FFmpeg path is not configured");

      const chunkSize = Number(job.payload.mergeGroupSize ?? 0);
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merging OK tracks…",
        progress: 92,
      });
      await mergeAudioByVersion({
        versionType: "OK",
        chunkSize,
        inputDir: outputDirOk,
        outputDir: mergedOkDir,
        ffmpegPath,
      });

      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merging ALT tracks…",
        progress: 96,
      });
      await mergeAudioByVersion({
        versionType: "ALT",
        chunkSize,
        inputDir: outputDirAlt,
        outputDir: mergedAltDir,
        ffmpegPath,
      });
    } else if (job.payload.mergeEnabled && deferred > 0) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merge skipped (waiting for pending Suno downloads)",
        progress: 99,
      });
    }
  }

  private async runGenerate(job: JobItem) {
    if (job.payload.jobType !== "workflow") return undefined;
    const songDraftProvider = job.payload.songDraftProvider ?? "deepseek";
    const deepseekApiKey = songDraftProvider === "deepseek" ? job.payload.deepseekApiKey || process.env.DEEPSEEK_API_KEY : "";
    const slaiSongApiKey =
      songDraftProvider === "slai" ? job.payload.slaiSongApiKey || process.env.SLAI_SONG_API_KEY || process.env.SLAI_API_KEY : "";
    const slaiSongModel = String(job.payload.slaiSongModel || "").trim();

    if (songDraftProvider === "deepseek" && !deepseekApiKey) throw new Error("DeepSeek API key is not configured");
    if (songDraftProvider === "slai" && !slaiSongApiKey) throw new Error("SLAI Song API key is not configured");

    const description = job.payload.description ?? "";
    const structure = job.payload.structure ?? "";
    const language = job.payload.language ?? "English";
    const creativity = Number.isFinite(job.payload.creativity) ? (job.payload.creativity as number) : 55;
    const batchId = job.payload.batchId;
    const uniqueOpening = job.payload.uniqueOpening;
    const strictLevel = job.payload.strictLevel;
    const historyWindow = job.payload.uniquenessHistoryWindow ?? 100;
    const db = job.payload.db;
    const descriptionTitle = job.payload.descriptionTitle ?? "";
    const structureTitle = job.payload.structureTitle ?? "";
    const profileOkId = job.payload.profileOkId;
    const profileAltId = job.payload.profileAltId;
    const sunoAutoSubmit = Boolean(job.payload.sunoAutoSubmit);
    const sunoApiKey = String(job.payload.sunoApiKey || "").trim();
    const sunoCallbackUrl = String(job.payload.sunoCallbackUrl || "").trim();
    const sunoVersion = job.payload.sunoVersion ?? "v5.5";
    const sunoOutputDirOk = String(job.payload.sunoOutputDirOk || "").trim();
    const sunoOutputDirAlt = String(job.payload.sunoOutputDirAlt || "").trim() || sunoOutputDirOk;
    const batchIndex = typeof job.payload.batchIndex === "number" && Number.isFinite(job.payload.batchIndex) ? Math.floor(job.payload.batchIndex) : undefined;

    if (!db) throw new Error("Postgres database is not configured. Set Database settings and run Migrate.");

    cleanupBatchAlbums();
    const batchKey = batchId ?? job.jobId;

    const existingBatchAlbum = batchAlbumByBatchId.get(batchKey);
    const fixedAlbum = existingBatchAlbum?.album;

    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "workflow",
      status: "running",
      message: "Writing the song…",
      progress: 20,
      action: "generate",
    });
    console.log("[jobQueue] generate start", {
      jobId: job.jobId,
      provider: songDraftProvider,
      model: songDraftProvider === "slai" ? slaiSongModel || "gpt-5.5" : "deepseek-chat",
      language,
      creativity,
      descriptionChars: description.length,
      structureChars: structure.length,
      uniqueOpening: Boolean(uniqueOpening),
      strictLevel: strictLevel ?? 3,
      historyWindow,
    });

    const avoid = await getAvoidLists(db, historyWindow);

    let draft: { title: string; album: string; lyricsRaw: string } | null = null;
    let lastDraftError: unknown = null;
    let forcedAlbum: string | undefined = fixedAlbum;
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      const attemptStartedAt = Date.now();
      const picked = await getPooled(db, { opening: Boolean(uniqueOpening), title: true, album: !forcedAlbum });
      if (!picked.title) throw new Error("Title pool is empty. Seed Postgres table title_pool.");
      if (!forcedAlbum) {
        if (!picked.album) throw new Error("Album pool is empty. Seed Postgres table album_pool.");
        forcedAlbum = picked.album;
        batchAlbumByBatchId.set(batchKey, { album: forcedAlbum, createdAtMs: Date.now() });
      }
      const forcedOpening =
        uniqueOpening && picked.opening?.line1 && picked.opening?.line2 ? `${picked.opening.line1}\n${picked.opening.line2}` : undefined;
      if (uniqueOpening && !forcedOpening) throw new Error("Opening pool is empty. Seed Postgres table opening_pairs.");

      try {
        console.log("[jobQueue] generate attempt", { jobId: job.jobId, attempt, provider: songDraftProvider });
        draft =
          songDraftProvider === "slai"
            ? await generateSongDraftWithSlai({
                apiKey: slaiSongApiKey,
                model: slaiSongModel || undefined,
                language,
                creativity,
                description,
                structure,
                uniqueOpening,
                strictLevel,
                avoidTitles: avoid.titles,
                avoidAlbums: avoid.albums,
                avoidOpenings: avoid.openings,
                forcedTitle: picked.title,
                forcedAlbum,
                forcedOpening,
              })
            : await generateSongDraftWithDeepSeek({
                apiKey: deepseekApiKey,
                language,
                creativity,
                description,
                structure,
                uniqueOpening,
                strictLevel,
                avoidTitles: avoid.titles,
                avoidAlbums: avoid.albums,
                avoidOpenings: avoid.openings,
                forcedTitle: picked.title,
                forcedAlbum,
                forcedOpening,
              });
        console.log("[jobQueue] generate draft ok", {
          jobId: job.jobId,
          attempt,
          provider: songDraftProvider,
          ms: Date.now() - attemptStartedAt,
          titleChars: draft.title.length,
          albumChars: draft.album.length,
          lyricsChars: draft.lyricsRaw.length,
        });
        break;
      } catch (e) {
        console.log("[jobQueue] generate attempt failed", {
          jobId: job.jobId,
          attempt,
          provider: songDraftProvider,
          ms: Date.now() - attemptStartedAt,
          message: e instanceof Error ? e.message : String(e || ""),
        });
        lastDraftError = e;
        draft = null;
      }
    }

    if (!draft) {
      const msg = lastDraftError instanceof Error ? lastDraftError.message : String(lastDraftError || "");
      throw new Error(`Failed to generate song draft after retries${msg ? `: ${msg}` : ""}`);
    }

    const lyricsPolished = draft.lyricsRaw;

    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "workflow",
      status: "running",
      message: "Saving your song…",
      progress: 90,
      action: "generate",
    });

    const createdAt = new Date().toISOString();
    const songUid = randomUUID();

    if (db) {
      await upsertSong(db, {
        songUid,
        title: draft.title,
        album: draft.album,
        lyricsRaw: draft.lyricsRaw,
        lyricsPolished,
        songDescription: description,
        songStructure: structure,
        language,
        creativity,
        batchId,
        batchIndex,
        status: "generated",
        createdAtIso: createdAt,
      });
      await insertHistory(db, { kind: "song_generated", message: `${draft.title} / ${draft.album}`, songUid });
    }

    const outSong = {
      id: songUid,
      title: draft.title,
      album: draft.album,
      lyricsRaw: draft.lyricsRaw,
      lyricsPolished,
      batchIndex,
      songDescriptionTitle: descriptionTitle,
      songStructureTitle: structureTitle,
      songDescription: description,
      songStructure: structure,
      profileOkId,
      profileAltId,
      language,
      creativity,
      batchId,
      createdAt,
    };
    if (sunoAutoSubmit && db && sunoOutputDirOk) {
      const model: SunoApiModel = sunoVersion === "v5" ? "V5" : "V5_5";
      this.sunoSubmitter.enqueue({
        jobId: job.jobId,
        db,
        apiKey: sunoApiKey,
        callbackUrl: sunoCallbackUrl,
        model,
        song: outSong,
        outputDirOk: sunoOutputDirOk,
        outputDirAlt: sunoOutputDirAlt,
      });
    }

    return outSong;
  }
}
