"use client";

import { useEffect, useRef, useState } from "react";

import { computePeaks } from "@/lib/studio-peaks";

/**
 * Peak waveform for a clip or song (shared by the clip inspector, the song detail
 * rail and the timeline clips). Decodes the real audio.
 *
 * The canvas used to stay blank whenever the fetch or decode failed — a cross-origin
 * audio host without CORS headers is enough — so a clip looked like a flat colour block
 * with no hint that anything was wrong (QA C1). It now always paints something: peaks
 * when they arrive, a dim baseline when they cannot, and `data-waveform` records which.
 *
 * Peaks are cached per URL at a fixed resolution (see `lib/studio-peaks.ts`), so
 * zooming a clip (which remounts its canvas) repaints from memory instead of decoding
 * the file again.
 */

export type WaveformProps = {
  url: string | null | undefined;
  width: number;
  height: number;
  className?: string;
  label: string;
  /** Peak bar colour; defaults to the studio green. */
  color?: string;
};

type WaveformState = "pending" | "ready" | "fallback";

export function Waveform({ url, width, height, className, label, color = "#52d17c" }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [state, setState] = useState<WaveformState>("pending");

  useEffect(() => {
    if (!url) {
      setState("fallback");
      return;
    }
    let cancelled = false;
    setState("pending");
    void computePeaks(url).then((peaks) => {
      if (cancelled) return;
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      const w = canvas?.width ?? width;
      const h = canvas?.height ?? height;
      if (!peaks || peaks.length === 0) {
        // The baseline is CSS (see [data-waveform="fallback"]); do not touch the canvas,
        // which also keeps jsdom from logging its not-implemented 2d context.
        setState("fallback");
        return;
      }
      if (ctx) {
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = color;
        for (let x = 0; x < w; x += 1) {
          const peak = peaks[Math.min(peaks.length - 1, Math.floor((x / w) * peaks.length))] ?? 0;
          const bar = Math.max(1, peak * h * 0.9);
          ctx.fillRect(x, (h - bar) / 2, 1, bar);
        }
      }
      setState("ready");
    });
    return () => {
      cancelled = true;
    };
  }, [url, color, width, height]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      width={width}
      height={height}
      role="img"
      aria-label={label}
      data-waveform={state}
    />
  );
}
