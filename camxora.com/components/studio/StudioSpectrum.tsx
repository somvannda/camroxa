"use client";

import { useEffect, useRef } from "react";

/**
 * Master spectrum (category: "not evidenced" features).
 *
 * The reference has no master spectrum surface; this is a deliberate addition requested
 * after the parity audit. It reads the analyser the engine already puts on the master bus,
 * so it measures the real output instead of a synthesised curve.
 */

export function StudioSpectrum({ analyser }: { analyser: AnalyserNode | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    if (!analyser) {
      context.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    const bins = new Uint8Array(analyser.frequencyBinCount);
    let frame = 0;
    const draw = () => {
      analyser.getByteFrequencyData(bins);
      const width = canvas.width;
      const height = canvas.height;
      context.clearRect(0, 0, width, height);
      // Log-ish spacing: the first third of the bins carries most musical content.
      const bars = 32;
      for (let bar = 0; bar < bars; bar += 1) {
        const from = Math.floor((bar / bars) ** 2 * bins.length);
        const to = Math.max(from + 1, Math.floor(((bar + 1) / bars) ** 2 * bins.length));
        let peak = 0;
        for (let index = from; index < to; index += 1) peak = Math.max(peak, bins[index] ?? 0);
        const barHeight = Math.max(1, (peak / 255) * height);
        context.fillStyle = peak > 180 ? "#a855f7" : "#8b90a6";
        context.fillRect(bar * 4, height - barHeight, 2, barHeight);
      }
      frame = window.requestAnimationFrame(draw);
    };
    draw();
    return () => window.cancelAnimationFrame(frame);
  }, [analyser]);

  return (
    <canvas
      ref={canvasRef}
      className="se-spectrum"
      width={128}
      height={26}
      role="img"
      aria-label="Master spectrum"
    />
  );
}
