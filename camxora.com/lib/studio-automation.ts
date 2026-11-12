/**
 * Track volume automation.
 *
 * Points live on the track document as absolute timeline seconds and values on the
 * track's 0-100 volume scale. Playback and the offline renderer both schedule the same
 * linear ramps, so what you draw is what the export hears.
 */

export type AutomationPoint = {
  id: string;
  time: number;
  value: number;
};

export type AutomationLane = "volume" | "pan";

export function sanitizeAutomation(
  input: unknown,
  min: number,
  max: number
): AutomationPoint[] {
  if (!Array.isArray(input)) return [];
  return input
    .map((raw) => {
      if (!raw || typeof raw !== "object") return null;
      const point = raw as Record<string, unknown>;
      const time = Number(point.time);
      const value = Number(point.value);
      if (!Number.isFinite(time) || !Number.isFinite(value)) return null;
      return {
        id: typeof point.id === "string" && point.id ? point.id : `auto-${time}`,
        time: Math.max(0, time),
        value: Math.min(max, Math.max(min, value)),
      };
    })
    .filter((point): point is AutomationPoint => point !== null)
    .sort((a, b) => a.time - b.time);
}

/** Linearly interpolated value at a timeline position, holding the ends. */
export function automationValueAt(
  points: AutomationPoint[],
  at: number,
  fallback: number
): number {
  if (points.length === 0) return fallback;
  if (at <= points[0].time) return points[0].value;
  const last = points[points.length - 1];
  if (at >= last.time) return last.value;
  for (let index = 1; index < points.length; index += 1) {
    const right = points[index];
    if (at > right.time) continue;
    const left = points[index - 1];
    const span = right.time - left.time;
    if (span <= 0) return right.value;
    const ratio = (at - left.time) / span;
    return left.value + (right.value - left.value) * ratio;
  }
  return last.value;
}

/**
 * Schedule a volume curve on a gain parameter.
 *
 * `from` is the transport position in seconds, `when` the AudioContext time it maps
 * to, and `rate` the audition-speed factor. Values are normalised from the track's
 * 0-100 scale to the gain node's 0-1 scale.
 */
/**
 * Schedule a pan curve on a StereoPannerNode's `pan` parameter. Values are the
 * track's -100..100 scale, normalised to the node's -1..1 range.
 */
export function schedulePanAutomation(
  param: AudioParam,
  points: AutomationPoint[],
  {
    from,
    when,
    rate = 1,
    fallback,
  }: { from: number; when: number; rate?: number; fallback: number }
): void {
  if (points.length === 0) return;
  const scale = (value: number) => Math.max(-1, Math.min(1, value / 100));
  param.cancelScheduledValues(when);
  param.setValueAtTime(scale(automationValueAt(points, from, fallback)), when);
  for (const point of points) {
    if (point.time <= from) continue;
    param.linearRampToValueAtTime(
      scale(point.value),
      when + (point.time - from) / Math.max(0.1, rate)
    );
  }
}

export function scheduleVolumeAutomation(
  param: AudioParam,
  points: AutomationPoint[],
  {
    from,
    when,
    rate = 1,
    fallback,
  }: { from: number; when: number; rate?: number; fallback: number }
): void {
  if (points.length === 0) return;
  const scale = (value: number) => Math.max(0, Math.min(1, value / 100));
  param.cancelScheduledValues(when);
  param.setValueAtTime(scale(automationValueAt(points, from, fallback)), when);
  for (const point of points) {
    if (point.time <= from) continue;
    param.linearRampToValueAtTime(
      scale(point.value),
      when + (point.time - from) / Math.max(0.1, rate)
    );
  }
}
