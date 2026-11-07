"use client";

import { useEffect, useRef } from "react";

/**
 * Peak waveform for a clip or song (shared by the clip inspector and the song detail
 * rail). Decodes the real audio; a failed fetch or decode leaves the canvas blank and
 * every panel keeps its metadata. Guarded for jsdom/SSR where AudioContext is absent.
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

export function Waveform({ url, width, height, className, label, color = "#52d17c" }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!url || typeof AudioContext === "undefined") return;
    let cancelled = false;
    const context = new AudioContext();
    void fetch(url)
      .then((response) => (response.ok ? response.arrayBuffer() : null))
      .then((buffer) => (buffer ? context.decodeAudioData(buffer) : null))
      .then((decoded) => {
        if (cancelled || !decoded) return;
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext("2d");
        if (!canvas || !ctx) return;
        const data = decoded.getChannelData(0);
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = color;
        const step = Math.max(1, Math.floor(data.length / w));
        for (let x = 0; x < w; x += 1) {
          let peak = 0;
          for (let i = 0; i < step; i += 1) {
            const value = Math.abs(data[x * step + i] ?? 0);
            if (value > peak) peak = value;
          }
          const bar = Math.max(1, peak * h * 0.9);
          ctx.fillRect(x, (h - bar) / 2, 1, bar);
        }
      })
      .catch(() => {
        /* no audio: the caller keeps its metadata */
      });
    return () => {
      cancelled = true;
      void context.close();
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
