"use client";

import { useEffect, useState } from "react";

import { computePeaks } from "@/lib/studio-peaks";
import { detectTempo } from "@/lib/studio-tempo";

/**
 * Tempo tag for a library song row (§19.2): the reference shows key and BPM; our
 * generation payload carries neither, so the tempo is measured from the audio instead of
 * guessed. Key stays absent — a mixed song has no single reliable key to report.
 *
 * Decoding is lazy and cached per URL by `computePeaks`, and the row renders nothing until
 * a confident reading exists (pads and one-shots keep no tempo tag).
 */

const tempoCache = new Map<string, number | null>();

export function SongTempo({ url, duration }: { url?: string | null; duration?: number | null }) {
  const [bpm, setBpm] = useState<number | null>(() => (url ? tempoCache.get(url) ?? null : null));

  useEffect(() => {
    if (!url || !(duration && duration > 0)) return;
    if (tempoCache.has(url)) {
      setBpm(tempoCache.get(url) ?? null);
      return;
    }
    let cancelled = false;
    void computePeaks(url).then((peaks) => {
      const guess = detectTempo(peaks, duration);
      const value = guess ? Math.round(guess.bpm) : null;
      tempoCache.set(url, value);
      if (!cancelled) setBpm(value);
    });
    return () => {
      cancelled = true;
    };
  }, [url, duration]);

  if (!bpm) return null;
  return <span>{bpm} BPM</span>;
}
