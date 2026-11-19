/**
 * Disk side of the download coordinator.
 *
 * A download is written to `<name>.camxora-part-<uuid>` in the target folder and
 * only renamed over the real name once every byte arrived. A cancel, a failure
 * or a quit therefore never leaves a half-written MP3 behind.
 */
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { once } from "node:events";
import type { DownloadIo, DownloadSink } from "./download-coordinator";

export const PART_SUFFIX = ".camxora-part-";

class FileSink implements DownloadSink {
  private stream: fs.WriteStream | null;
  private closed = false;

  constructor(
    private readonly tempPath: string,
    private readonly targetPath: string,
    stream: fs.WriteStream,
  ) {
    this.stream = stream;
  }

  static async create(targetPath: string): Promise<FileSink> {
    const directory = path.dirname(targetPath);
    await fs.promises.mkdir(directory, { recursive: true });
    const tempPath = path.join(
      directory,
      `${path.basename(targetPath)}${PART_SUFFIX}${randomUUID()}`,
    );
    const stream = fs.createWriteStream(tempPath, { flags: "wx" });
    await once(stream, "open");
    return new FileSink(tempPath, targetPath, stream);
  }

  write(chunk: Uint8Array): Promise<void> {
    const stream = this.stream;
    if (!stream) return Promise.reject(new Error("The download stream is closed."));
    return new Promise((resolve, reject) => {
      stream.write(chunk, (error) => {
        if (error) reject(error);
        else resolve();
      });
    });
  }

  async commit(): Promise<void> {
    const stream = this.stream;
    if (!stream) throw new Error("The download stream is closed.");
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error) => reject(error);
      stream.once("error", onError);
      stream.end(() => {
        stream.off("error", onError);
        resolve();
      });
    });
    this.stream = null;
    this.closed = true;
    await fs.promises.rename(this.tempPath, this.targetPath);
  }

  async abort(): Promise<void> {
    this.destroy();
    await fs.promises.rm(this.tempPath, { force: true }).catch(() => undefined);
  }

  abortSync(): void {
    this.destroy();
    try {
      fs.rmSync(this.tempPath, { force: true });
    } catch {
      // The temp file may already be gone; quitting must not throw.
    }
  }

  private destroy(): void {
    if (this.closed) return;
    this.closed = true;
    const stream = this.stream;
    this.stream = null;
    if (!stream) return;
    stream.destroy();
  }
}

async function fileSize(filePath: string): Promise<number | null> {
  try {
    const stat = await fs.promises.stat(filePath);
    return stat.isFile() && stat.size > 0 ? stat.size : null;
  } catch {
    return null;
  }
}

export function createNodeDownloadIo(): DownloadIo {
  return {
    ensureDir: async (directory) => {
      await fs.promises.mkdir(directory, { recursive: true });
    },
    createSink: (targetPath) => FileSink.create(targetPath),
    fileSize,
  };
}
