import path from "node:path";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import { randomUUID } from "node:crypto";
import { BrowserWindow, app, ipcMain } from "electron";
import type { VideoExportSettings, VideoRenderEvent } from "../shared/app-types";

type WebglExportJob = {
  jobId: string;
  mp3Path: string;
  backgroundPath: string;
  logoPath?: string;
  template: unknown;
  width: number;
  height: number;
  fps: number;
};

type WebglExportReadyPayload = { jobId: string; duration: number };

const jobs = new Map<string, WebglExportJob>();
const readyResolvers = new Map<string, (p: WebglExportReadyPayload) => void>();
let registered = false;

export function registerWebglExportIpc() {
  if (registered) return;
  registered = true;

  ipcMain.handle("mg:webglExport:getJob", async (_evt, input: { jobId: string }) => {
    const jobId = String(input?.jobId || "").trim();
    const job = jobs.get(jobId);
    if (!job) return { ok: false as const, message: "WebGL export job not found" };
    return { ok: true as const, job };
  });

  ipcMain.on("mg:webglExport:ready", (_evt, payload: WebglExportReadyPayload) => {
    const jobId = String(payload?.jobId || "").trim();
    const r = readyResolvers.get(jobId);
    if (!r) return;
    readyResolvers.delete(jobId);
    r({ jobId, duration: Number(payload?.duration || 0) });
  });
}

export async function runWebglVideoRender(input: {
  ffmpegPath: string;
  exportSettings: VideoExportSettings;
  preloadPath: string;
  devServerUrl?: string;
  mp3Path: string;
  backgroundPath: string;
  outputDir: string;
  outputName: string;
  logoPath?: string;
  template: unknown;
  width: number;
  height: number;
  fps: number;
  runId: string;
  onEvent: (evt: VideoRenderEvent) => void;
  shouldCancel: () => boolean;
}): Promise<{ ok: true; outputPath: string } | { ok: false; message: string }> {
  registerWebglExportIpc();

  const w = Math.max(64, Math.min(8192, Math.floor(Number(input.width) || 1920)));
  const h = Math.max(64, Math.min(8192, Math.floor(Number(input.height) || 1080)));
  const fps = Math.max(1, Math.min(60, Math.floor(Number(input.fps) || 30)));

  await fs.mkdir(input.outputDir, { recursive: true });
  const outPath = path.join(input.outputDir, input.outputName);
  const jobId = randomUUID();

  const job: WebglExportJob = {
    jobId,
    mp3Path: input.mp3Path,
    backgroundPath: input.backgroundPath,
    logoPath: input.logoPath,
    template: input.template,
    width: w,
    height: h,
    fps,
  };
  jobs.set(jobId, job);

  const win = new BrowserWindow({
    width: w,
    height: h,
    show: false,
    useContentSize: true,
    backgroundColor: "#000000",
    webPreferences: {
      preload: input.preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      offscreen: true,
    },
  });

  try {
    if (input.devServerUrl) {
      await win.loadURL(`${input.devServerUrl}?webglExportJobId=${encodeURIComponent(jobId)}`);
    } else {
      const indexHtmlPath = path.join(app.getAppPath(), "dist", "index.html");
      await win.loadFile(indexHtmlPath, { query: { webglExportJobId: jobId } });
    }

    const ready = await new Promise<WebglExportReadyPayload>((resolve, reject) => {
      const t = setTimeout(() => {
        readyResolvers.delete(jobId);
        reject(new Error("WebGL export runner timed out"));
      }, 20000);
      readyResolvers.set(jobId, (p) => {
        clearTimeout(t);
        resolve(p);
      });
    });

    const duration = Math.max(0, Number(ready.duration) || 0);
    if (!Number.isFinite(duration) || duration <= 0) return { ok: false, message: "Invalid audio duration for WebGL export" };

    const totalFrames = Math.max(1, Math.ceil(duration * fps));
    const preset = input.exportSettings.preset;
    const crf = Math.max(10, Math.min(40, Math.floor(input.exportSettings.crf)));
    const audioBitrate = `${input.exportSettings.audioBitrateKbps}k`;

    const ffmpegArgs = [
      "-hide_banner",
      "-y",
      "-f",
      "rawvideo",
      "-pix_fmt",
      "bgra",
      "-s",
      `${w}x${h}`,
      "-r",
      String(fps),
      "-i",
      "-",
      "-i",
      input.mp3Path,
      "-c:v",
      "libx264",
      "-preset",
      preset,
      "-crf",
      String(crf),
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      audioBitrate,
      "-shortest",
      "-movflags",
      "+faststart",
      outPath,
    ];

    const ff = spawn(input.ffmpegPath, ffmpegArgs, { windowsHide: true });
    let ffErr = "";
    ff.stderr.on("data", (d) => {
      ffErr += String(d || "");
    });

    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    const waitDrain = () =>
      new Promise<void>((resolve, reject) => {
        ff.stdin.once("drain", () => resolve());
        ff.stdin.once("error", (e) => reject(e));
      });

    const startTs = Date.now();
    for (let frame = 0; frame < totalFrames; frame += 1) {
      if (input.shouldCancel()) {
        try {
          ff.kill();
        } catch {
        }
        return { ok: false, message: "Export stopped by user." };
      }
      const targetMs = Math.round((frame / fps) * 1000);
      const nowMs = Date.now() - startTs;
      const waitMs = targetMs - nowMs;
      if (waitMs > 0) await sleep(waitMs);

      const image = await win.webContents.capturePage();
      const bmp = image.toBitmap();
      if (bmp.length !== w * h * 4) {
        try {
          ff.kill();
        } catch {
        }
        return { ok: false, message: `WebGL frame size mismatch (${bmp.length} bytes)` };
      }

      if (!ff.stdin.write(bmp)) await waitDrain();

      const progress = frame / totalFrames;
      input.onEvent({
        runId: input.runId,
        status: "running",
        message: `Rendering ${frame + 1}/${totalFrames}`,
        progress,
        frame: frame + 1,
        totalFrames,
        outputPath: outPath,
      });
    }

    ff.stdin.end();

    const exitCode: number = await new Promise((resolve, reject) => {
      ff.on("error", reject);
      ff.on("close", (code) => resolve(code ?? -1));
    });

    if (exitCode !== 0) return { ok: false, message: String(ffErr || `ffmpeg exited with code ${exitCode}`).trim() };

    input.onEvent({ runId: input.runId, status: "done", message: "Done", progress: 1, outputPath: outPath });
    return { ok: true, outputPath: outPath };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : "WebGL export failed" };
  } finally {
    jobs.delete(jobId);
    try {
      win.destroy();
    } catch {
    }
  }
}

