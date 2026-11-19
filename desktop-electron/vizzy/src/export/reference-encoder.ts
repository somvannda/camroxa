/**
 * Reference-compatible WASM MP4 encoder.
 *
 * Vizzy ships `export/encodeworkers.js` plus a custom Emscripten encoder. The
 * worker is fed transferred RGBA frames and planar Float32 audio, and writes
 * encoded MP4 bytes back at absolute file offsets. When a file target is
 * available the chunks are written straight to it, so memory stays bounded even
 * for full-length 1080p exports.
 */
import type { Project } from "../domain/project";
import type { StageRenderer } from "../renderer/renderer";
import type { ExportOptions, ExportResult } from "./exporter";

const AUDIO_WINDOW = 1152;
const PRESETS = [
  "ultrafast",
  "superfast",
  "veryfast",
  "faster",
  "fast",
  "medium",
  "slow",
  "slower",
  "veryslow",
];
const PROFILES = ["baseline", "main", "high"];

type VideoConfig = {
  width: number;
  height: number;
  fps: number;
  bitrate: number;
  presetIdx: number;
  duration: number;
  profileIdx: number;
  crf: number;
};

type AudioConfig = { bitrate: number; sampleRate: number };

export class ReferenceWasmExporter {
  static supported(): boolean {
    return typeof Worker !== "undefined";
  }

  async export(
    renderer: StageRenderer,
    project: Project,
    options: ExportOptions,
  ): Promise<ExportResult> {
    const width = Math.max(16, Math.round(options.width));
    const height = Math.max(16, Math.round(options.height));
    const fps = Math.max(1, Math.round(options.fps));
    const duration = Math.max(0.1, options.duration);
    const total = Math.max(1, Math.round(duration * fps));
    const start = Math.max(0, options.startTime ?? 0);
    const restore = renderer.setExportSize(width, height);

    const worker = new Worker(new URL("export/encodeworkers.js", document.baseURI));
    const writer = options.streamTarget?.getWriter() ?? null;
    const chunks: { position: number; data: Uint8Array }[] = [];
    let streamedBytes = 0;
    let pendingOffset: number | null = null;
    let writeChain: Promise<void> = Promise.resolve();
    let readyResolve: (() => void) | null = null;
    let readyReject: ((error: Error) => void) | null = null;
    let loadResolve: (() => void) | null = null;
    let initResolve: (() => void) | null = null;
    let closeResolve: (() => void) | null = null;
    let closedSeen = false;
    let failure: Error | null = null;
    let terminated = false;

    const fail = (error: Error): void => {
      failure = error;
      readyReject?.(error);
      readyResolve = null;
      readyReject = null;
      loadResolve?.();
      loadResolve = null;
      initResolve?.();
      initResolve = null;
      closeResolve?.();
      closeResolve = null;
    };

    const handleChunk = (data: Uint8Array): void => {
      if (pendingOffset === null) {
        // Without a file target the worker returns one complete buffer after
        // the "closed" message.
        if (!writer) {
          chunks.push({ position: 0, data: new Uint8Array(data) });
          if (closedSeen) {
            closeResolve?.();
            closeResolve = null;
          }
        }
        return;
      }
      const position = pendingOffset;
      pendingOffset = null;
      writeChain = writeChain
        .then(async () => {
          if (writer) {
            const payload =
              data.buffer instanceof ArrayBuffer
                ? (data as Uint8Array<ArrayBuffer>)
                : new Uint8Array(data);
            await writer.write({ type: "write", position, data: payload });
          } else {
            chunks.push({ position, data: new Uint8Array(data) });
          }
          streamedBytes += data.byteLength;
        })
        .catch((error) => fail(error instanceof Error ? error : new Error(String(error))));
    };

    worker.onmessage = (event: MessageEvent) => {
      const message = event.data as
        | { action: string; [key: string]: unknown }
        | Uint8Array;
      if (message instanceof Uint8Array) {
        handleChunk(message);
        if (closedSeen && !writer) {
          closeResolve?.();
          closeResolve = null;
        }
        return;
      }
      switch (message.action) {
        case "log":
          break;
        case "loaded":
          loadResolve?.();
          loadResolve = null;
          break;
        case "initialized":
          initResolve?.();
          initResolve = null;
          break;
        case "flush_to_file":
          pendingOffset = Number(message.offset) || 0;
          break;
        case "ready":
          readyResolve?.();
          readyResolve = null;
          readyReject = null;
          break;
        case "closed":
          closedSeen = true;
          if (writer) {
            writeChain
              .then(async () => {
                await writer.close();
                closeResolve?.();
                closeResolve = null;
              })
              .catch((error) => fail(error instanceof Error ? error : new Error(String(error))));
          }
          break;
        case "error":
        case "initialize-error": {
          const detail =
            String(message.errMsg ?? "") ||
            String(message.errTitle ?? "") ||
            "reference encoder failed";
          fail(new Error(detail));
          break;
        }
        default:
          break;
      }
    };
    worker.onerror = (event) => fail(new Error(event.message || "encoder worker failed"));

    const waitFor = (
      assign: (resolve: () => void) => void,
      trigger: () => void,
    ): Promise<void> =>
      new Promise((resolve, reject) => {
        assign(() => {
          if (failure) reject(failure);
          else resolve();
        });
        readyReject = reject;
        trigger();
      });

    try {
      await waitFor(
        (resolve) => {
          loadResolve = resolve;
        },
        () => worker.postMessage({ action: "load", data: "sequential" }),
      );
      if (failure) throw failure;

      const sampleRate = options.audioBuffer?.sampleRate ?? 48000;
      const videoConfig: VideoConfig = {
        width,
        height,
        fps,
        bitrate: (options.bitrate ?? 0) > 0 ? (options.bitrate ?? 0) * 1_000_000 : 0,
        presetIdx: Math.max(0, PRESETS.indexOf(options.preset ?? "veryfast")),
        duration,
        profileIdx: Math.max(0, PROFILES.indexOf(options.profile ?? "high")),
        crf: Math.min(51, Math.max(0, options.crf ?? 20)),
      };
      const audioConfig: AudioConfig = {
        bitrate: Math.max(32, options.audioBitrate ?? 192) * 1000,
        sampleRate,
      };

      await waitFor(
        (resolve) => {
          initResolve = resolve;
        },
        () =>
          worker.postMessage({
            action: "init",
            data: {
              audioConfig,
              videoConfig,
              usingFileSystem: Boolean(writer),
            },
          }),
      );
      if (failure) throw failure;

      const audio =
        options.audioBuffer ??
        new AudioBuffer({
          length: Math.max(1, Math.ceil(duration * sampleRate)),
          numberOfChannels: 2,
          sampleRate,
        });
      const audioWindow = (index: number): Float32Array => {
        const base = Math.round(start * sampleRate) + index * AUDIO_WINDOW;
        const out = new Float32Array(AUDIO_WINDOW * 2);
        for (let channel = 0; channel < 2; channel += 1) {
          const source = audio.getChannelData(Math.min(channel, audio.numberOfChannels - 1));
          for (let sample = 0; sample < AUDIO_WINDOW; sample += 1) {
            const value = source[base + sample];
            out[channel * AUDIO_WINDOW + sample] = Number.isFinite(value) ? value : 0;
          }
        }
        return out;
      };

      let time = start;
      let videoFrames = 0;
      let audioFrames = 0;
      const windowSeconds = AUDIO_WINDOW / sampleRate;

      const waitReady = (): Promise<void> =>
        new Promise((resolve, reject) => {
          readyResolve = resolve;
          readyReject = reject;
        });

      while (videoFrames < total) {
        if (options.shouldCancel?.()) {
          throw new DOMException("Export cancelled", "AbortError");
        }
        let ready: Promise<void>;
        if (time - start + 1e-9 >= audioFrames * windowSeconds) {
          const frame = audioWindow(audioFrames);
          audioFrames += 1;
          ready = waitReady();
          worker.postMessage({ action: "audio" });
          worker.postMessage(frame, [frame.buffer]);
        } else {
          await options.beforeFrame?.(time);
          renderer.render(time);
          const frame = renderer.readFrame(false);
          time += 1 / fps;
          videoFrames += 1;
          ready = waitReady();
          worker.postMessage({ action: "video" });
          worker.postMessage(frame, [frame.buffer]);
          options.onProgress(videoFrames, total, "rendering frames");
        }
        await ready;
        if (failure) throw failure;
      }

      await new Promise<void>((resolve, reject) => {
        closeResolve = resolve;
        readyReject = reject;
        worker.postMessage({ action: "close", shouldReturnFile: true });
      });
      if (failure) throw failure;
      await writeChain;
      if (failure) throw failure;

      if (writer) {
        return {
          blob: new Blob([], { type: "video/mp4" }),
          filename: "out.mp4",
          frames: total,
          encodeMs: 0,
          hadAudio: Boolean(options.audioBuffer),
          streamed: true,
          bytes: streamedBytes,
        };
      }

      const size = chunks.reduce(
        (max, chunk) => Math.max(max, chunk.position + chunk.data.byteLength),
        0,
      );
      const output = new Uint8Array(size);
      for (const chunk of chunks) output.set(chunk.data, chunk.position);
      return {
        blob: new Blob([output], { type: "video/mp4" }),
        filename: "out.mp4",
        frames: total,
        encodeMs: 0,
        hadAudio: Boolean(options.audioBuffer),
      };
    } finally {
      restore();
      if (!terminated) {
        terminated = true;
        try {
          worker.terminate();
        } catch {
          /* already gone */
        }
      }
      if (writer && failure) {
        try {
          await writer.abort(failure);
        } catch {
          /* already closed */
        }
      }
      void project;
    }
  }
}
