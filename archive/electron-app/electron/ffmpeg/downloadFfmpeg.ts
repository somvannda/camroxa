import { promises as fs } from "node:fs";
import path from "node:path";
import AdmZip from "adm-zip";

async function ensureDir(p: string) {
  await fs.mkdir(p, { recursive: true });
}

async function writeFile(p: string, data: ArrayBuffer) {
  await ensureDir(path.dirname(p));
  await fs.writeFile(p, Buffer.from(data));
}

async function exists(p: string) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function findFfmpegExe(rootDir: string): Promise<string | null> {
  const stack: string[] = [rootDir];
  while (stack.length) {
    const dir = stack.pop();
    if (!dir) continue;
    let entries: { name: string; isDirectory(): boolean; isFile(): boolean }[] = [];
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) stack.push(full);
      else if (e.isFile() && e.name.toLowerCase() === "ffmpeg.exe") return full;
    }
  }
  return null;
}

export async function downloadFfmpeg(opts: { installDir: string }) {
  const url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip";
  const installDir = path.resolve(opts.installDir);
  const tmpDir = path.join(installDir, ".mg-tmp");
  await ensureDir(tmpDir);

  const zipPath = path.join(tmpDir, "ffmpeg.zip");

  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Download failed (${res.status}): ${body.slice(0, 200)}`);
  }

  const buf = await res.arrayBuffer();
  await writeFile(zipPath, buf);

  const targetDir = path.join(installDir, "ffmpeg");
  await ensureDir(targetDir);

  const zip = new AdmZip(zipPath);
  zip.extractAllTo(targetDir, true);

  const ffmpegExe = await findFfmpegExe(targetDir);
  if (!ffmpegExe || !(await exists(ffmpegExe))) throw new Error("ffmpeg.exe not found after extraction");

  await fs.rm(tmpDir, { recursive: true, force: true }).catch(() => undefined);

  return { ok: true as const, ffmpegPath: ffmpegExe, installDir: targetDir };
}

