import { existsSync } from "node:fs";
import type { Song } from "../../shared/app-types";
import type { DbCfg } from "../db/songStore";
import { listSongsByBatchId } from "../db/songStore";
import { getSunoTaskByRequestHash, upsertSunoTask } from "../db/sunoTaskStore";
import { buildSunoOutputPaths, downloadToFile, hashSunoGenerateRequest, sunoApiGenerate, sunoApiTryGetTracks, type SunoApiModel } from "./sunoApi";

export type SunoSubmitterItem = {
  jobId: string;
  db: DbCfg;
  apiKey: string;
  callbackUrl: string;
  model: SunoApiModel;
  song: Song;
  outputDirOk: string;
  outputDirAlt: string;
};

export type SunoSubmitterEvent =
  | { jobId: string; status: "running"; message: string; progress?: number }
  | { jobId: string; status: "failed"; message: string; progress?: number }
  | { jobId: string; status: "completed"; message: string; progress?: number };

export class SunoSubmitter {
  private queue: SunoSubmitterItem[] = [];
  private running = 0;
  private batchIndexCache = new Map<string, Map<string, number>>();

  constructor(
    private readonly opts: {
      maxConcurrent: number;
      onEvent?: (e: SunoSubmitterEvent) => void;
    },
  ) {}

  enqueue(item: SunoSubmitterItem) {
    this.queue.push(item);
    this.pump();
  }

  private pump() {
    while (this.running < this.opts.maxConcurrent && this.queue.length) {
      const item = this.queue.shift();
      if (!item) return;
      this.running += 1;
      void this.runOne(item)
        .catch(() => undefined)
        .finally(() => {
          this.running -= 1;
          this.pump();
        });
    }
  }

  private async trackNoForSong(db: DbCfg, song: Song) {
    const batchId = String(song.batchId ?? "").trim();
    if (!batchId) return undefined;
    const songUid = String(song.id || "").trim();
    if (!songUid) return undefined;
    let idx = this.batchIndexCache.get(batchId);
    if (!idx) {
      const songs = await listSongsByBatchId(db, batchId);
      idx = new Map(songs.map((s, i) => [s.id, i + 1] as const));
      this.batchIndexCache.set(batchId, idx);
    }
    return idx.get(songUid);
  }

  private emit(e: SunoSubmitterEvent) {
    this.opts.onEvent?.(e);
  }

  private async runOne(item: SunoSubmitterItem) {
    const apiKey = String(item.apiKey || "").trim();
    if (!apiKey) {
      this.emit({ jobId: item.jobId, status: "failed", message: "Suno auto-submit skipped: missing API key" });
      return;
    }
    const callbackUrl = String(item.callbackUrl || "").trim() || "https://api.example.com/callback";

    const prompt = item.song.lyricsPolished || item.song.lyricsRaw;
    const requestHash = hashSunoGenerateRequest({
      model: item.model,
      title: item.song.title,
      prompt,
      style: item.song.songDescription,
      instrumental: false,
    });

    this.emit({ jobId: item.jobId, status: "running", message: `Suno: submitting (${item.song.title})` });

    const cached = await getSunoTaskByRequestHash(item.db, requestHash);
    const outputDirOk = String(item.outputDirOk || "").trim();
    const outputDirAlt = String(item.outputDirAlt || "").trim() || outputDirOk;
    const trackNo = typeof item.song.batchIndex === "number" && Number.isFinite(item.song.batchIndex) ? Math.floor(item.song.batchIndex) : await this.trackNoForSong(item.db, item.song);

    if (cached?.audioUrlOk && cached.audioUrlAlt) {
      const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: item.song.title, trackNo });
      const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: item.song.title, trackNo });
      if (!existsSync(pathsOk.ok)) await downloadToFile(cached.audioUrlOk, pathsOk.ok);
      if (!existsSync(pathsAlt.alt)) await downloadToFile(cached.audioUrlAlt, pathsAlt.alt);
      this.emit({ jobId: item.jobId, status: "completed", message: `Suno: downloaded cached (${item.song.title})` });
      return;
    }

    let taskId = String(cached?.taskId || "").trim();
    if (!taskId) {
      const gen = await sunoApiGenerate({
        apiKey,
        model: item.model,
        title: item.song.title,
        lyrics: prompt,
        style: item.song.songDescription,
        instrumental: false,
        callbackUrl,
      });
      taskId = gen.taskId;
    }

    await upsertSunoTask(item.db, {
      requestHash,
      songUid: item.song.id,
      batchId: item.song.batchId ?? "",
      trackNo,
      model: item.model,
      title: item.song.title,
      style: item.song.songDescription,
      instrumental: false,
      taskId,
      status: "PENDING",
      outputDirOk,
      outputDirAlt,
    });

    const r = await sunoApiTryGetTracks(apiKey, taskId);
    if (r.audioUrls.length >= 2) {
      const okUrl = String(r.audioUrls[0] || "").trim();
      const altUrl = String(r.audioUrls[1] || "").trim();
      await upsertSunoTask(item.db, {
        requestHash,
        songUid: item.song.id,
        batchId: item.song.batchId ?? "",
        trackNo,
        model: item.model,
        title: item.song.title,
        style: item.song.songDescription,
        instrumental: false,
        taskId,
        status: String(r.status || "SUCCESS"),
        audioUrlOk: okUrl,
        audioUrlAlt: altUrl,
        outputDirOk,
        outputDirAlt,
      });

      const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: item.song.title, trackNo });
      const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: item.song.title, trackNo });
      if (okUrl && !existsSync(pathsOk.ok)) await downloadToFile(okUrl, pathsOk.ok);
      if (altUrl && !existsSync(pathsAlt.alt)) await downloadToFile(altUrl, pathsAlt.alt);
      this.emit({ jobId: item.jobId, status: "completed", message: `Suno: downloaded (${item.song.title})` });
      return;
    }

    this.emit({ jobId: item.jobId, status: "completed", message: `Suno: submitted (${item.song.title})` });
  }
}
