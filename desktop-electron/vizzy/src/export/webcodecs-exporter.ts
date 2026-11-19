/**
 * WebCodecs export backend.
 *
 * The reference exposes Wasm (x264) and an experimental WebCodecs encoder. This
 * uses mediabunny's CanvasSource/AudioBufferSource over the browser's native
 * VideoEncoder/AudioEncoder and muxes straight into MP4 or WebM, so it avoids
 * the ffmpeg.wasm frame ladder and its 2 GB in-memory ceiling.
 */
import {
  AudioBufferSource,
  BufferTarget,
  CanvasSource,
  Mp4OutputFormat,
  Output,
  QUALITY_HIGH,
  StreamTarget,
  WebMOutputFormat,
  canEncodeVideo,
} from "mediabunny";
import type { Project } from "../domain/project";
import type { StageRenderer } from "../renderer/renderer";
import type { ExportCodec, ExportOptions, ExportResult } from "./exporter";

function videoCodec(codec: ExportCodec): "avc" | "vp9" | "vp8" {
  if (codec === "h264") return "avc";
  return codec;
}

function audioCodec(codec: ExportCodec): "aac" | "opus" {
  return codec === "h264" ? "aac" : "opus";
}

function sliceAudioBuffer(
  buffer: AudioBuffer,
  start: number,
  duration: number,
): AudioBuffer {
  const sampleRate = buffer.sampleRate;
  const from = Math.max(0, Math.floor(start * sampleRate));
  const to = Math.min(buffer.length, Math.ceil((start + duration) * sampleRate));
  const length = Math.max(1, to - from);
  const sliced = new AudioBuffer({
    length,
    numberOfChannels: buffer.numberOfChannels,
    sampleRate,
  });
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    sliced.copyToChannel(buffer.getChannelData(channel).subarray(from, to), channel);
  }
  return sliced;
}

export class WebCodecsExporter {
  static available(): boolean {
    return typeof VideoEncoder !== "undefined";
  }

  static async supports(
    codec: ExportCodec,
    width: number,
    height: number,
    fps: number,
  ): Promise<boolean> {
    if (!WebCodecsExporter.available()) return false;
    try {
      return await canEncodeVideo(videoCodec(codec), {
        width: Math.max(2, Math.round(width)),
        height: Math.max(2, Math.round(height)),
        frameRate: fps,
      });
    } catch {
      return false;
    }
  }

  async export(
    renderer: StageRenderer,
    project: Project,
    options: ExportOptions,
  ): Promise<ExportResult> {
    const codec = videoCodec(options.codec ?? "h264");
    const format = codec === "avc" ? new Mp4OutputFormat() : new WebMOutputFormat();
    const streamWriter = options.streamTarget?.getWriter();
    let streamedBytes = 0;
    const countedStream =
      options.streamTarget && streamWriter
        ? new WritableStream<{
            type: "write";
            data: Uint8Array<ArrayBuffer>;
            position: number;
          }>({
            write(chunk) {
              streamedBytes += chunk.data.byteLength;
              return streamWriter.write(chunk);
            },
            close() {
              return streamWriter.close();
            },
            abort(reason) {
              return streamWriter.abort(reason);
            },
          })
        : null;
    const streamTarget = countedStream
      ? new StreamTarget(countedStream, { chunked: true })
      : null;
    const target = streamTarget ?? new BufferTarget();
    const output = new Output({ format, target });
    const restore = renderer.setExportSize(options.width, options.height);
    const started = performance.now();
    const total = Math.max(1, Math.round(options.duration * options.fps));
    const start = Math.max(0, options.startTime ?? 0);

    try {
      const video = new CanvasSource(renderer.canvasElement, {
        codec,
        ...(options.bitrate && options.bitrate > 0
          ? { bitrate: options.bitrate * 1_000_000 }
          : { quality: QUALITY_HIGH }),
        keyFrameInterval: 2,
      });
      output.addVideoTrack(video, { frameRate: options.fps });

      let audio: AudioBufferSource | null = null;
      if (options.audioBuffer) {
        audio = new AudioBufferSource({
          codec: audioCodec(options.codec ?? "h264"),
          bitrate: Math.max(32, options.audioBitrate ?? 192) * 1000,
        });
        output.addAudioTrack(audio);
      }

      await output.start();
      if (audio && options.audioBuffer) {
        await audio.add(
          sliceAudioBuffer(options.audioBuffer, start, options.duration),
        );
      }

      for (let frame = 0; frame < total; frame += 1) {
        if (options.shouldCancel?.()) {
          throw new DOMException("Export cancelled", "AbortError");
        }
        const time = (start + frame / options.fps) % Math.max(0.001, project.duration);
        await options.beforeFrame?.(time);
        renderer.render(time);
        await video.add(frame / options.fps, 1 / options.fps);
        options.onProgress(frame + 1, total, "encoding frames");
      }

      await output.finalize();
      const extension = format.fileExtension.replace(/^\./, "");
      if (streamTarget) {
        return {
          blob: new Blob([], { type: format.mimeType }),
          filename: `out.${extension}`,
          frames: total,
          encodeMs: performance.now() - started,
          hadAudio: Boolean(audio),
          streamed: true,
          bytes: streamedBytes,
        };
      }
      const buffer = (target as BufferTarget).buffer;
      if (!buffer) throw new Error("WebCodecs produced no output");
      return {
        blob: new Blob([buffer], { type: format.mimeType }),
        filename: `out.${extension}`,
        frames: total,
        encodeMs: performance.now() - started,
        hadAudio: Boolean(audio),
      };
    } finally {
      restore();
    }
  }
}
