/**
 * Arrangement snapping and drag thresholds (roadmap G7, G8).
 *
 * Kept pure so the behaviour can be unit-tested once the harness lands (W5.1):
 * the reference snaps to the grid and shows a guideline, but the interesting part is
 * the arithmetic, not the pixels.
 */

/** Pointer travel (px) before a press becomes a drag rather than a click (G8). */
export const DRAG_THRESHOLD_PX = 3;

/**
 * Snap a time (seconds) to the nearest subdivision of a bar.
 *
 * @param seconds      absolute position of the clip start
 * @param secondsPerBar seconds in one bar (from tempo + signature)
 * @param divisions    subdivisions per bar; 4 = beats, 8 = eighth notes
 */
export function snapToGrid(seconds: number, secondsPerBar: number, divisions = 4): number {
  if (!Number.isFinite(seconds) || secondsPerBar <= 0 || divisions <= 0) return Math.max(0, seconds);
  const step = secondsPerBar / divisions;
  const snapped = Math.round(seconds / step) * step;
  return Math.max(0, Number(snapped.toFixed(6)));
}

/**
 * Convert a horizontal drag into a new clip start.
 *
 * @param originStart  the clip's start when the drag began
 * @param deltaPx      pointer movement since then
 * @param barPx        width of one bar in pixels
 * @param secondsPerBar seconds in one bar
 * @param divisions    snap subdivisions per bar (0 disables snapping)
 */
export function dragToStart(
  originStart: number,
  deltaPx: number,
  barPx: number,
  secondsPerBar: number,
  divisions = 4
): number {
  if (barPx <= 0) return originStart;
  const raw = originStart + (deltaPx / barPx) * secondsPerBar;
  if (divisions <= 0) return Math.max(0, raw);
  return snapToGrid(raw, secondsPerBar, divisions);
}

/** True once the pointer has moved far enough to count as a drag. */
export function isDrag(deltaPx: number, threshold = DRAG_THRESHOLD_PX): boolean {
  return Math.abs(deltaPx) > threshold;
}

/**
 * Double (`direction` 1) or halve (-1) the snap grid, clamped to 1..32
 * subdivisions per bar. The captured "Double / Halve Grid Density" pair.
 */
export function scaleGrid(divisions: number, direction: 1 | -1): number {
  const base = Number.isFinite(divisions) && divisions > 0 ? Math.round(divisions) : 4;
  return direction > 0 ? Math.min(32, base * 2) : Math.max(1, Math.floor(base / 2));
}
