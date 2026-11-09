"use client";

import { useEffect, useRef } from "react";

/**
 * Peak waveform for a clip or song (shared by the clip inspector, the song detail
 * rail and the timeline clips). Decodes the real audio; a failed fetch or decode
 * leaves the canvas blank and every panel keeps its metadata. Guarded for jsdom/SSR
 * where AudioContext is absent.
 *
 * Peaks are cached per URL at a fixed resolution, so zooming a clip (which remounts
 * its canvas) repaints from memory instead of decoding the file again.
 */

const PEAK_BUCKETS = 1024;
const peakCache = new Map<string, Promise<number[] | null>>();

function computePeaks(url: string): Promise<number[] | null> {
  const cached = peakCache.get(url);
  if (cached) return cached;
  const pending = (async () => {
    if (typeof AudioContext === "undefined") return null;
    const context = new AudioContext();
    try {
      const response = await fetch(url);
      if (!response.ok) return null;
      const decoded = await context.decodeAudioData(await response.arrayBuffer());
      const data = decoded.getChannelData(0);
      const step = Math.max(1, Math.floor(data.length / PEAK_BUCKETS));
      const peaks: number[] = [];
      for (let bucket = 0; bucket < PEAK_BUCKETS; bucket += 1) {
        let peak = 0;
        for (let i = 0; i < step; i += 1) {
          const value = Math.abs(data[bucket * step + i] ?? 0);
          if (value > peak) peak = value;
        }
        peaks.push(peak);
      }
      return peaks;
    } catch {
      return null;
    } finally {
      void context.close();
    }
  })();
  peakCache.set(url, pending);
  return pending;
}

export type WaveformProps = {
  url: string | null | undefined;
  width: number;
  height: number;
  className?: string;
  label: string;
  /** Peak bar colour; defaults to the studio green. */
  color?: string;
};

export function Waveform({ url, width, height, className, label, color = "#52d17c" }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    void computePeaks(url).then((peaks) => {
      if (cancelled || !peaks) return;
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color;
      for (let x = 0; x < w; x += 1) {
        const peak = peaks[Math.min(peaks.length - 1, Math.floor((x / w) * peaks.length))] ?? 0;
        const bar = Math.max(1, peak * h * 0.9);
        ctx.fillRect(x, (h - bar) / 2, 1, bar);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [url, color]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      width={width}
      height={height}
      role="img"
      aria-label={label}
    />
  );
}
