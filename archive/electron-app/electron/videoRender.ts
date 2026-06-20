import path from "node:path";
import { spawn } from "node:child_process";
import { ipcMain } from "electron";
import type { VideoRenderEvent, VideoRenderStartInput } from "../shared/app-types";

type RunVideoRenderOptions = {
  pythonPath: string;
  ffmpegPath: string;
  appPath: string;
  input: VideoRenderStartInput;
  runId: string;
  onEvent: (evt: VideoRenderEvent) => void;
};

export async function runVideoRender(opts: RunVideoRenderOptions): Promise<{ ok: true; outputPath: string } | { ok: false; message: string }> {
  const pythonPath = String(opts.pythonPath || "").trim() || "python";
  const ffmpegPath = String(opts.ffmpegPath || "").trim();
  if (!ffmpegPath) return { ok: false, message: "FFmpeg path is not configured" };

  const mp3Path = String(opts.input.mp3Path || "").trim();
  const backgroundPath = String(opts.input.backgroundPath || "").trim();
  const outputDir = String(opts.input.outputDir || "").trim();
  const templatePath = String(opts.input.templatePath || "").trim();
  const templateJsonB64 = String((opts.input as { templateJsonB64?: string }).templateJsonB64 || "").trim();
  const logoPath = String(opts.input.logoPath || "").trim();
  const fps = Math.max(1, Math.min(60, Math.floor(Number(opts.input.fps ?? 30) || 30)));
  const width = Math.max(64, Math.min(8192, Math.floor(Number(opts.input.width ?? 1920) || 1920)));
  const height = Math.max(64, Math.min(8192, Math.floor(Number(opts.input.height ?? 1080) || 1080)));
  const renderer = (opts.input as { renderer?: string }).renderer === "cpu" ? "cpu" : "gpu";
  const previewPngPath = String((opts.input as { previewPngPath?: string }).previewPngPath || "").trim();
  const previewFrame = Math.max(0, Math.floor(Number((opts.input as { previewFrame?: number }).previewFrame ?? 150) || 150));

  if (!mp3Path) return { ok: false, message: "MP3 path is required" };
  if (!backgroundPath) return { ok: false, message: "Background image path is required" };
  if (!outputDir) return { ok: false, message: "Output directory is required" };

  const visualizerRoot = path.join(opts.appPath, "visualizer");
  const resolvedTemplatePath = templatePath || path.join(visualizerRoot, "templates", "default.json");

  const args = [
    "-m",
    "visualizer.main",
    mp3Path,
    resolvedTemplatePath,
    "--background",
    backgroundPath,
    "--outputDir",
    outputDir,
    "--ffmpeg",
    ffmpegPath,
    "--renderer",
    renderer,
    "--fps",
    String(fps),
    "--width",
    String(width),
    "--height",
    String(height),
  ];
  if (previewPngPath) {
    args.push("--previewPng");
    args.push(previewPngPath);
    args.push("--previewFrame");
    args.push(String(previewFrame));
  }
  if (templateJsonB64) {
    args.push("--templateB64");
    args.push(templateJsonB64);
  }
  if (logoPath) {
    args.push("--logo");
    args.push(logoPath);
  }

  const child = spawn(pythonPath, args, {
    windowsHide: true,
    cwd: opts.appPath,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
    },
  });

  let stdoutBuf = "";
  let stderrBuf = "";
  let lastOutputPath = "";

  const flushLines = () => {
    while (true) {
      const idx = stdoutBuf.indexOf("\n");
      if (idx < 0) return;
      const line = stdoutBuf.slice(0, idx).trim();
      stdoutBuf = stdoutBuf.slice(idx + 1);
      if (!line) continue;

      if (!line.startsWith("MG_EVENT ")) {
        console.log(`[videoRender stdout]: ${line}`);
        continue;
      }
      const payload = line.slice("MG_EVENT ".length);
      try {
        const evt = JSON.parse(payload) as Partial<VideoRenderEvent>;
        if (evt.outputPath) lastOutputPath = String(evt.outputPath);
        if (evt.status === "failed") {
          console.error(`[videoRender] MG_EVENT failed: ${String(evt.message || "")}`);
        }
        opts.onEvent({
          runId: opts.runId,
          status: (evt.status as VideoRenderEvent["status"]) ?? "running",
          message: String(evt.message || ""),
          progress: typeof evt.progress === "number" ? evt.progress : undefined,
          frame: typeof evt.frame === "number" ? evt.frame : undefined,
          totalFrames: typeof evt.totalFrames === "number" ? evt.totalFrames : undefined,
          outputPath: evt.outputPath ? String(evt.outputPath) : undefined,
        });
      } catch {
        continue;
      }
    }
  };

  child.stdout.on("data", (chunk) => {
    stdoutBuf += String(chunk || "");
    flushLines();
  });

  child.stderr.on("data", (chunk) => {
    const s = String(chunk || "");
    stderrBuf += s;
    console.error(`[videoRender stderr]: ${s}`);
  });

  let isKilled = false;
  
  // We attach a small listener on the electron app side to allow manual killing
  const onStop = () => {
      isKilled = true;
      try { child.kill(); } catch {}
  };
  ipcMain.once("mg:videoRender:stop", onStop);

  return await new Promise((resolve) => {
    const finish = (res: any) => {
        ipcMain.removeListener("mg:videoRender:stop", onStop);
        resolve(res);
    };
    child.on("error", (e) => {
      console.error("[videoRender] Failed to start python process:", e);
      finish({ ok: false, message: e instanceof Error ? e.message : "Failed to start python process" });
    });
    child.on("exit", (code) => {
      if (isKilled) return finish({ ok: false, message: "Export stopped by user." });
      console.log(`[videoRender] Python process exited with code ${code}`);
      if (code === 0 && lastOutputPath) return finish({ ok: true, outputPath: lastOutputPath });
      const err = String(stderrBuf || "").trim();
      if (err) {
        console.error(`[videoRender] Python stderr:\n${err}`);
        return finish({ ok: false, message: err.split("\n").slice(-6).join("\n") });
      }
      finish({ ok: false, message: `Video render failed (exit code ${code ?? "unknown"})` });
    });
  });
}
