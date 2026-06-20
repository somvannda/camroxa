import path from "node:path";
import { promises as fs } from "node:fs";
import type { ImageSampleFile } from "../shared/app-types";

const supportedExts = new Set([".png", ".jpg", ".jpeg", ".webp"]);

export function isSupportedImageFileName(fileName: string) {
  const ext = path.extname(fileName).toLowerCase();
  return supportedExts.has(ext);
}

export async function listImagesInFolder(folderPath: string): Promise<ImageSampleFile[]> {
  const dirents = await fs.readdir(folderPath, { withFileTypes: true });
  const items: ImageSampleFile[] = [];
  for (const d of dirents) {
    if (!d.isFile()) continue;
    if (!isSupportedImageFileName(d.name)) continue;
    const filePath = path.join(folderPath, d.name);
    const st = await fs.stat(filePath);
    items.push({
      filePath,
      fileUrl: `mgsamples://file?path=${encodeURIComponent(filePath)}`,
      fileName: d.name,
      mtimeMs: st.mtimeMs,
    });
  }
  items.sort((a, b) => a.fileName.localeCompare(b.fileName));
  return items;
}
