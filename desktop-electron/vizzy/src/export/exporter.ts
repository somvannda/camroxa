import { FFmpeg } from "@ffmpeg/ffmpeg";
import coreURL from "@ffmpeg/core?url";
import wasmURL from "@ffmpeg/core/wasm?url";
import type { Project } from "../domain/project";
import type { StageRenderer } from "../renderer/renderer";

export interface ExportAudio {
  name: string;
  bytes: Uint8Array;
}

export type ExportCodec = "h264" | "vp9" | "vp8";

export interface ExportOptions {
  width: number;
  height: number;
  fps: number;
  duration: number;
  /** Absolute project time of the first exported frame. */
  startTime?: number;
  /** Output codec; the ladder still falls back when ffmpeg cannot encode it. */
  codec?: ExportCodec;
  /** Video bitrate in Mbps; 0 lets x264 pick a CRF (or VP8/9 use 4 Mbps). */
  bitrate?: number;
  /** x264 constant-rate factor, used when `bitrate` is 0. */
  crf?: number;
  /** x264 speed preset (veryfast, medium, slow, ...). */
  preset?: string;
  /** H.264 profile (baseline / main / high). */
  profile?: string;
  /** Audio bitrate in kbps. */
  audioBitrate?: number;
  /** Audio track to mux with the rendered frames, if any. */
  audio?: ExportAudio;
  /** Decoded audio for the WebCodecs backend (avoids decoding twice). */
  audioBuffer?: AudioBuffer;
  /** When set, the WebCodecs backend streams container chunks at these positions. */
  streamTarget?: WritableStream<{
    type: "write";
    data: Uint8Array<ArrayBuffer>;
    position: number;
  }>;
  /** Runs before each frame is captured, so animation state advances with the clock. */
  beforeFrame?(time: number): void | Promise<void>;
  /** Return true to abort the export (checked between frames and segments). */
  shouldCancel?(): boolean;
  onProgress(done: number, total: number, stage: string): void;
}

export interface ExportResult {
  blob: Blob;
  filename: string;
  frames: number;
  encodeMs: number;
  hadAudio: boolean;
  /** True when the bytes were written directly to `streamTarget`. */
  streamed?: boolean;
  /** Output size when streamed (the blob is empty in that case). */
  bytes?: number;
}

interface Attempt {
  args: string[];
  name: string;
  mime: string;
  audio: boolean;
}

/**
 * Raw frames held in ffmpeg's memory at once. 30 frames at 720p is ~110 MB,
 * which keeps peak memory bounded while still giving the encoder a decent
 * batch per invocation.
 */
const RAW_SEGMENT_FRAMES = 30;

/**
 * Frame-by-frame export through ffmpeg.wasm.
 *
 * The stage is rendered at the export resolution (not the preview size), each
 * frame is written into ffmpeg's virtual filesystem, and the optional audio
 * track is muxed in the same pass. Encoder selection degrades: H.264 + AAC in
 * MP4, then MPEG-4 + AAC, then VP8 + Vorbis in WebM.
 */
export class Exporter {
  private ffmpeg: FFmpeg | null = null;
  private loaded = false;

  private async ensureLoaded(onProgress: ExportOptions["onProgress"]): Promise<FFmpeg> {
    if (this.ffmpeg && this.loaded) return this.ffmpeg;
    onProgress(0, 1, "loading ffmpeg core");
    const ffmpeg = new FFmpeg();
    await ffmpeg.load({ coreURL, wasmURL });
    this.ffmpeg = ffmpeg;
    this.loaded = true;
    return ffmpeg;
  }

  /** Drop the wasm instance after a cancel/failure, freeing its heap. */
  reset(): void {
    try {
      this.ffmpeg?.terminate();
    } catch {
      /* already stopped */
    }
    this.ffmpeg = null;
    this.loaded = false;
  }

  private checkCancel(options: ExportOptions): void {
    if (options.shouldCancel?.()) {
      throw new DOMException("Export cancelled", "AbortError");
    }
  }

  private attempts(options: ExportOptions, audioName: string | null): Attempt[] {
    const { fps } = options;
    const input = ["-framerate", String(fps), "-i", "frame_%04d.png"];
    const start = Math.max(0, options.startTime ?? 0);
    const audioInput = audioName
      ? start > 0
        ? ["-ss", String(start), "-t", String(options.duration), "-i", audioName]
        : ["-i", audioName]
      : [];
    const map = audioName ? ["-map", "0:v:0", "-map", "1:a:0", "-shortest"] : [];
    const bitrate = Number(options.bitrate) || 0;
    const crf = Math.min(51, Math.max(0, Number(options.crf ?? 20)));
    const preset = options.preset || "veryfast";
    const profile = options.profile || "high";
    const audioBitrate = Math.max(32, Number(options.audioBitrate ?? 192));

    const video = (codec: ExportCodec): string[] => {
      if (codec === "h264") {
        return [
          "-c:v", "libx264", "-pix_fmt", "yuv420p",
          ...(bitrate > 0 ? ["-b:v", `${bitrate}M`] : ["-crf", String(crf)]),
          "-preset", preset,
          "-profile:v", profile,
        ];
      }
      if (codec === "vp9") {
        return ["-c:v", "libvpx-vp9", "-b:v", `${bitrate > 0 ? bitrate : 4}M`];
      }
      return ["-c:v", "libvpx", "-b:v", `${bitrate > 0 ? bitrate : 4}M`];
    };
    const audioCodec = (codec: ExportCodec): string[] =>
      audioName
        ? [
            "-c:a",
            codec === "h264" ? "aac" : codec === "vp9" ? "libopus" : "libvorbis",
            "-b:a",
            `${audioBitrate}k`,
          ]
        : [];
    const attempt = (codec: ExportCodec): Attempt => {
      const container = codec === "h264" ? "mp4" : "webm";
      return {
        args: [
          ...input,
          ...audioInput,
          ...map,
          ...video(codec),
          ...audioCodec(codec),
          `out.${container}`,
        ],
        name: `out.${container}`,
        mime: codec === "h264" ? "video/mp4" : "video/webm",
        audio: Boolean(audioName),
      };
    };

    const primary = options.codec ?? "h264";
    const order: ExportCodec[] =
      primary === "h264"
        ? ["h264", "vp8"]
        : primary === "vp9"
          ? ["vp9", "vp8", "h264"]
          : ["vp8", "h264"];
    return order.map(attempt);
  }

  async export(
    renderer: StageRenderer,
    project: Project,
    options: ExportOptions,
  ): Promise<ExportResult> {
    const { width, height, fps, duration } = options;
    const total = Math.max(1, Math.round(duration * fps));
    const ffmpeg = await this.ensureLoaded(options.onProgress);
    this.checkCancel(options);

    const started = performance.now();
    const restore = renderer.setExportSize(width, height);

    let audioName: string | null = null;
    if (options.audio) {
      this.checkCancel(options);
      audioName = options.audio.name;
      // ffmpeg.wasm transfers the buffer to its worker, which detaches it on the
      // main thread. Write a copy so the project's audio bytes survive and a
      // second export can reuse them.
      await ffmpeg.writeFile(audioName, options.audio.bytes.slice());
    }

    // Raw capture keeps peak memory bounded by encoding short segments; it also
    // avoids PNG compression per frame, which made long 1080p exports run out of
    // ffmpeg.wasm memory. PNG frames remain only as a fallback.
    const useRaw = true;
    let rawError: unknown = null;
    try {
      if (useRaw) {
        try {
          return await this.exportRaw(ffmpeg, renderer, project, options, audioName, started);
        } catch (error) {
          rawError = error;
          console.error("raw export failed", error);
          options.onProgress(
            0,
            total,
            `raw capture failed (${error instanceof Error ? error.message : String(error)})`,
          );
        }
      }
      // The PNG ladder writes every frame into the wasm heap. That is only
      // viable for short clips; for long exports it guarantees an out-of-memory
      // failure, so surface the raw error instead of wasting minutes.
      const pngBudget = Math.round(width) * Math.round(height) * total;
      if (rawError && pngBudget > 1_500_000_000) {
        throw rawError;
      }
      try {
        return await this.exportFrames(ffmpeg, renderer, project, options, audioName, started);
      } catch (error) {
        if (rawError) {
          const rawMessage =
            rawError instanceof Error ? rawError.message : String(rawError);
          const pngMessage = error instanceof Error ? error.message : String(error);
          throw new Error(`raw export failed: ${rawMessage}; PNG fallback failed: ${pngMessage}`);
        }
        throw error;
      }
    } finally {
      restore();
      for (let frame = 0; frame < total; frame += 1) {
        try {
          await ffmpeg.deleteFile(`frame_${String(frame).padStart(4, "0")}.png`);
        } catch {
          /* ignore */
        }
      }
      if (audioName) {
        try {
          await ffmpeg.deleteFile(audioName);
        } catch {
          /* ignore */
        }
      }
    }
  }

  /**
   * Raw-frame export: read the drawing buffer and feed ffmpeg rawvideo.
   *
   * Encoding a PNG costs seconds per frame at 720p because it reads the buffer
   * back *and* compresses on the main thread; the same readback costs
   * milliseconds. A whole export's raw frames would not fit in memory, so they
   * are written one segment at a time, encoded to VP8, then joined with the
   * audio track.
   */
  private async exportRaw(
    ffmpeg: FFmpeg,
    renderer: StageRenderer,
    project: Project,
    options: ExportOptions,
    audioName: string | null,
    started: number,
  ): Promise<ExportResult> {
    const { width, height, fps } = options;
    const total = Math.max(1, Math.round(options.duration * fps));
    const input = [
      "-f", "rawvideo",
      "-pix_fmt", "rgba",
      "-video_size", `${Math.round(width)}x${Math.round(height)}`,
      "-framerate", String(fps),
    ];
    const segments: string[] = [];
    const codec = options.codec ?? "vp8";
    const bitrate = Number(options.bitrate) || 0;
    const crf = Math.min(51, Math.max(0, Number(options.crf ?? 20)));
    const preset = options.preset || "veryfast";
    const profile = options.profile || "high";
    const audioBitrate = Math.max(32, Number(options.audioBitrate ?? 192));
    const container = codec === "h264" ? "mp4" : "webm";
    const segmentVideo =
      codec === "h264"
        ? [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            ...(bitrate > 0 ? ["-b:v", `${bitrate}M`] : ["-crf", String(crf)]),
            "-preset",
            preset,
            "-profile:v",
            profile,
          ]
        : codec === "vp9"
          ? [
              "-c:v",
              "libvpx-vp9",
              "-b:v",
              `${bitrate > 0 ? bitrate : 4}M`,
              "-pix_fmt",
              "yuv420p",
            ]
          : ["-c:v", "libvpx", "-b:v", `${bitrate > 0 ? bitrate : 4}M`, "-pix_fmt", "yuv420p"];
    // Keep each segment's raw frames under ~150 MB so 1080p/4K exports do not
    // exhaust the wasm heap.
    const bytesPerFrame = Math.max(1, Math.round(width) * Math.round(height) * 4);
    const segmentFrames = Math.max(
      2,
      Math.min(RAW_SEGMENT_FRAMES, Math.floor((150 * 1024 * 1024) / bytesPerFrame)),
    );

    for (let start = 0; start < total; start += segmentFrames) {
      const end = Math.min(total, start + segmentFrames);
      const names: string[] = [];
      for (let frame = start; frame < end; frame += 1) {
        this.checkCancel(options);
        const time = ((options.startTime ?? 0) + frame / fps) % Math.max(0.001, project.duration);
        await options.beforeFrame?.(time);
        renderer.render(time);
        const name = `frame_${String(frame).padStart(4, "0")}.rgba`;
        await ffmpeg.writeFile(name, renderer.readFrame());
        names.push(name);
        options.onProgress(frame + 1, total, "rendering frames");
      }

      this.checkCancel(options);
      const segment = `segment_${segments.length}.${container}`;
      options.onProgress(end, total, "encoding video");
      const code = await ffmpeg.exec([
        ...input,
        // The concat protocol stitches the segment's frames into one stream.
        "-i", `concat:${names.join("|")}`,
        ...segmentVideo,
        segment,
      ]);
      for (const name of names) {
        try {
          await ffmpeg.deleteFile(name);
        } catch {
          /* nothing to clean up */
        }
      }
      if (code !== 0) throw new Error(`ffmpeg exited ${code} encoding frames ${start + 1}-${end}`);
      segments.push(segment);
    }

    const list = "segments.txt";
    await ffmpeg.writeFile(
      list,
      new TextEncoder().encode(segments.map((segment) => `file '${segment}'`).join("\n") + "\n"),
    );
    this.checkCancel(options);
    options.onProgress(total, total, audioName ? "muxing audio" : "joining segments");
    const out = `out.${container}`;
    const start = Math.max(0, options.startTime ?? 0);
    const audioInput = audioName
      ? start > 0
        ? ["-ss", String(start), "-t", String(options.duration), "-i", audioName]
        : ["-i", audioName]
      : [];
    const audioCodec =
      codec === "h264"
        ? ["-c:a", "aac", "-b:a", `${audioBitrate}k`]
        : codec === "vp9"
          ? ["-c:a", "libopus", "-b:a", `${audioBitrate}k`]
          : ["-c:a", "libvorbis", "-b:a", `${audioBitrate}k`];
    const code = await ffmpeg.exec(
      audioName
        ? [
            "-f", "concat", "-safe", "0", "-i", list,
            ...audioInput,
            "-map", "0:v:0", "-map", "1:a:0", "-shortest",
            "-c:v", "copy", ...audioCodec,
            out,
          ]
        : ["-f", "concat", "-safe", "0", "-i", list, "-c:v", "copy", out],
    );
    if (code !== 0) throw new Error(`ffmpeg exited ${code} joining segments`);

    const data = await ffmpeg.readFile(out);
    const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
    const blob = new Blob([bytes as BlobPart], {
      type: container === "mp4" ? "video/mp4" : "video/webm",
    });

    for (const segment of segments) {
      try {
        await ffmpeg.deleteFile(segment);
      } catch {
        /* ignore */
      }
    }
    try {
      await ffmpeg.deleteFile(list);
      await ffmpeg.deleteFile(out);
    } catch {
      /* ignore */
    }

    return {
      blob,
      filename: out,
      frames: total,
      encodeMs: performance.now() - started,
      hadAudio: Boolean(audioName),
    };
  }

  /** Frame-by-frame fallback: PNG per frame, then an encoder ladder. */
  private async exportFrames(
    ffmpeg: FFmpeg,
    renderer: StageRenderer,
    project: Project,
    options: ExportOptions,
    audioName: string | null,
    started: number,
  ): Promise<ExportResult> {
    const { fps } = options;
    const total = Math.max(1, Math.round(options.duration * fps));

    for (let frame = 0; frame < total; frame += 1) {
      this.checkCancel(options);
      const time = ((options.startTime ?? 0) + frame / fps) % Math.max(0.001, project.duration);
      await options.beforeFrame?.(time);
      renderer.render(time);
      const blob = await renderer.frameBlob("image/png", 0.95, false);
      const bytes = new Uint8Array(await blob.arrayBuffer());
      await ffmpeg.writeFile(`frame_${String(frame).padStart(4, "0")}.png`, bytes);
      options.onProgress(frame + 1, total, "rendering frames");
    }

    let lastError: unknown = null;
    for (const attempt of this.attempts(options, audioName)) {
      options.onProgress(total, total, `encoding ${attempt.name}`);
      try {
        const code = await ffmpeg.exec(attempt.args);
        if (code !== 0) throw new Error(`ffmpeg exited ${code}`);
        const data = await ffmpeg.readFile(attempt.name);
        const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
        const blob = new Blob([bytes as BlobPart], { type: attempt.mime });
        return {
          blob,
          filename: attempt.name,
          frames: total,
          encodeMs: performance.now() - started,
          hadAudio: attempt.audio,
        };
      } catch (error) {
        lastError = error;
        try {
          await ffmpeg.deleteFile(attempt.name);
        } catch {
          /* nothing to clean up */
        }
      }
    }
    throw lastError instanceof Error ? lastError : new Error("encode failed");
  }
}
