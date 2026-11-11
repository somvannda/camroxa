/**
 * Audio peaks and onset positions, shared by the timeline waveform and the warp-marker
 * generator.
 *
 * The waveform used to own this cache; the audio clip editor needs the same peaks to
 * place warp markers on transients, so the decode lives here once. Peaks are cached per
 * URL, so repainting a clip or reopening the editor does not decode the file again.
 */

export const PEAK_BUCKETS = 1024;

const peakCache = new Map<string, Promise<number[] | null>>();

export function computePeaks(url: string): Promise<number[] | null> {
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

/**
 * Transient positions as 0–1 fractions of the clip.
 *
 * Works on the peak envelope: a marker goes wherever the envelope rises sharply out of
 * silence, with a minimum spacing so a busy section cannot produce a solid wall of
 * heads. Returns an empty list when the peaks are missing, so callers can fall back
 * to a grid instead of pretending they analysed audio.
 */
export function detectOnsets(
  peaks: number[] | null | undefined,
  { threshold = 0.12, minGap = 3 }: { threshold?: number; minGap?: number } = {}
): number[] {
  if (!peaks || peaks.length < 2) return [];
  const peak = peaks.reduce((max, value) => Math.max(max, value), 0);
  if (peak <= 0) return [];
  const normalised = peaks.map((value) => value / peak);
  const onsets: number[] = [0];
  let last = 0;
  for (let index = 1; index < normalised.length; index += 1) {
    const rise = normalised[index] - normalised[index - 1];
    if (rise < threshold) continue;
    if (index - last < minGap) continue;
    // A rise out of a quiet gap is an onset; a wobble inside a loud section is not.
    if (normalised[index - 1] > 0.55) continue;
    onsets.push(index / (normalised.length - 1));
    last = index;
  }
  return onsets;
}
