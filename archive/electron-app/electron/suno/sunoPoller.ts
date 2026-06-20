import { existsSync } from "node:fs";
import type { DbCfg } from "../db/sunoTaskStore";
import { listPendingSunoTasks, upsertSunoTask } from "../db/sunoTaskStore";
import { listSongsByBatchId } from "../db/songStore";
import { buildSunoOutputPaths, downloadToFile, sunoApiTryGetTracks } from "./sunoApi";

export async function pollAndDownloadPendingSuno(opts: {
  db: DbCfg;
  apiKey: string;
  outputDir: string;
  maxTasksPerRun?: number;
}) {
  const apiKey = String(opts.apiKey || "").trim();
  if (!apiKey) return { ok: false as const, message: "Suno API key is missing" };

  const outputDir = String(opts.outputDir || "").trim();
  if (!outputDir) return { ok: false as const, message: "Suno output directory is missing" };

  const limit = Math.max(1, Math.min(40, opts.maxTasksPerRun ?? 10));
  const tasks = await listPendingSunoTasks(opts.db, limit);
  if (!tasks.length) return { ok: true as const, checked: 0, downloaded: 0 };

  const batchIndexCache = new Map<string, Map<string, number>>();
  let downloaded = 0;
  for (const t of tasks) {
    const r = await sunoApiTryGetTracks(apiKey, t.taskId);
    const okUrl = r.audioUrls[0] ? String(r.audioUrls[0]) : null;
    const altUrl = r.audioUrls[1] ? String(r.audioUrls[1]) : null;
    await upsertSunoTask(opts.db, {
      requestHash: t.requestHash,
      songUid: t.songUid,
      batchId: t.batchId,
      model: t.model,
      title: t.title,
      style: t.style,
      instrumental: t.instrumental,
      taskId: t.taskId,
      status: String(r.status || ""),
      audioUrlOk: okUrl,
      audioUrlAlt: altUrl,
      outputDirOk: t.outputDirOk,
      outputDirAlt: t.outputDirAlt,
    });

    let trackNo: number | undefined = typeof t.trackNo === "number" && Number.isFinite(t.trackNo) ? Math.floor(t.trackNo) : undefined;
    if (!trackNo && t.batchId && t.songUid) {
      const batchId = String(t.batchId || "").trim();
      const songUid = String(t.songUid || "").trim();
      if (batchId && songUid) {
        let idx = batchIndexCache.get(batchId);
        if (!idx) {
          const songs = await listSongsByBatchId(opts.db, batchId);
          idx = new Map(
            songs.map((s, i) => [
              s.id,
              typeof s.batchIndex === "number" && Number.isFinite(s.batchIndex) ? Math.floor(s.batchIndex) : i + 1,
            ] as const),
          );
          batchIndexCache.set(batchId, idx);
        }
        trackNo = idx.get(songUid);
      }
    }

    if (okUrl) {
      const targetDir = String(t.outputDirOk || outputDir).trim() || outputDir;
      const paths = buildSunoOutputPaths({ outputDir: targetDir, title: t.title, trackNo });
      if (!existsSync(paths.ok)) {
        await downloadToFile(okUrl, paths.ok);
        downloaded += 1;
      }
    }
    if (altUrl) {
      const targetDir = String(t.outputDirAlt || t.outputDirOk || outputDir).trim() || outputDir;
      const paths = buildSunoOutputPaths({ outputDir: targetDir, title: t.title, trackNo });
      if (!existsSync(paths.alt)) {
        await downloadToFile(altUrl, paths.alt);
        downloaded += 1;
      }
    }
  }

  if (downloaded > 0) {
    console.log("[sunoPoller] downloaded", { checked: tasks.length, downloaded });
  }
  return { ok: true as const, checked: tasks.length, downloaded };
}
