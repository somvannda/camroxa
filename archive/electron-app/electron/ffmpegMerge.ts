import { promises as fs } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

export type MergeVersionType = "OK" | "ALT";

export type MergeRequest = {
  ffmpegPath: string;
  inputDir: string;
  outputDir: string;
  versionType: MergeVersionType;
  chunkSize: number;
};

export type MergeOutput = {
  outputFiles: string[];
  inputCounts: {
    OK: number;
    ALT: number;
  };
};

function nowStamp() {
  const d = new Date();
  const p = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function isAudioFile(fileName: string) {
  const lower = fileName.toLowerCase();
  return lower.endsWith(".mp3") || lower.endsWith(".wav") || lower.endsWith(".m4a");
}

function classify(fileName: string): MergeVersionType {
  const base = fileName.toUpperCase();
  if (base.includes("_ALT") || base.includes("-ALT")) return "ALT";
  return "OK";
}

function chunk<T>(items: T[], size: number) {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

async function runFfmpegConcat(ffmpegPath: string, listFilePath: string, outPath: string) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(ffmpegPath, ["-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", listFilePath, "-c", "copy", outPath], {
      windowsHide: true,
    });

    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || `ffmpeg exited with code ${code ?? -1}`));
    });
  });
}

export async function mergeAudioByVersion(req: MergeRequest): Promise<MergeOutput> {
  if (!Number.isFinite(req.chunkSize) || req.chunkSize < 0) throw new Error("chunkSize must be >= 0");

  const entries = await fs.readdir(req.inputDir, { withFileTypes: true });
  const files = entries
    .filter((e) => e.isFile())
    .map((e) => e.name)
    .filter(isAudioFile)
    .map((name) => ({
      name,
      fullPath: path.resolve(req.inputDir, name),
      version: classify(name),
    }));

  const okFiles = files.filter((f) => f.version === "OK");
  const altFiles = files.filter((f) => f.version === "ALT");
  const selected = req.versionType === "OK" ? okFiles : altFiles;

  await fs.mkdir(req.outputDir, { recursive: true });
  const stamp = nowStamp();

  const effectiveChunkSize = req.chunkSize === 0 ? selected.length : req.chunkSize;
  const chunks = chunk(selected, Math.max(1, effectiveChunkSize));
  const outputFiles: string[] = [];

  for (let i = 0; i < chunks.length; i++) {
    const listContent = chunks[i]
      .map((f) => {
        const safe = f.fullPath.replace(/'/g, "'\\''");
        return `file '${safe}'`;
      })
      .join("\n");

    const listFilePath = path.resolve(req.outputDir, `concat_${req.versionType}_${stamp}_${i + 1}.txt`);
    await fs.writeFile(listFilePath, listContent, "utf-8");

    const outPath = path.resolve(req.outputDir, `merged_${req.versionType}_${stamp}_${i + 1}.mp3`);
    await runFfmpegConcat(req.ffmpegPath, listFilePath, outPath);
    outputFiles.push(outPath);
  }

  return {
    outputFiles,
    inputCounts: {
      OK: okFiles.length,
      ALT: altFiles.length,
    },
  };
}
