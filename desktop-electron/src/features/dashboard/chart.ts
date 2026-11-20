/**
 * Geometry for the Weekly Usage chart.
 *
 * The page specification fixes the vertical formula:
 *   y = height − padding − (value / seriesMax) · (height − 2 · padding)
 * Each series is scaled by its own maximum.
 */
export const CHART_PADDING = 20;
export const GRID_LINE_COUNT = 4;

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

export function chartX(
  index: number,
  count: number,
  width: number,
  padding = CHART_PADDING,
): number {
  if (count <= 1) return width / 2;
  return padding + (index * (width - 2 * padding)) / (count - 1);
}

export function chartY(
  value: number,
  seriesMax: number,
  height: number,
  padding = CHART_PADDING,
): number {
  const max = seriesMax > 0 ? seriesMax : 0;
  const plotHeight = height - 2 * padding;
  if (max <= 0) return height - padding;
  const clamped = Math.max(0, Math.min(value, max));
  return height - padding - (clamped / max) * plotHeight;
}

export function seriesPoints(
  values: number[],
  width: number,
  height: number,
  padding = CHART_PADDING,
  maxOverride?: number,
): string {
  const max = maxOverride ?? Math.max(0, ...values);
  return values
    .map((value, index) => {
      const x = chartX(index, values.length, width, padding);
      const y = chartY(value, max, height, padding);
      return `${round(x)},${round(y)}`;
    })
    .join(" ");
}

/** Four evenly spaced dashed grid lines, top to bottom. */
export function gridLineYs(
  height: number,
  padding = CHART_PADDING,
  count = GRID_LINE_COUNT,
): number[] {
  const lines: number[] = [];
  if (count <= 1) return [padding];
  for (let index = 0; index < count; index += 1) {
    lines.push(round(padding + (index * (height - 2 * padding)) / (count - 1)));
  }
  return lines;
}

export interface ChartPoint {
  x: number;
  y: number;
}

/**
 * Monotone cubic path (Fritsch–Carlson tangents).
 *
 * Unlike a Catmull-Rom curve it never overshoots the data, so a zero day stays
 * on the baseline and a spike cannot dip below it. Control points are clamped
 * to the plot so a steep edge cannot paint outside the card either.
 */
export function monotonePath(points: ChartPoint[], minY?: number, maxY?: number): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${round(points[0].x)} ${round(points[0].y)}`;

  const n = points.length;
  const dx: number[] = [];
  const slopes: number[] = [];
  for (let index = 0; index < n - 1; index += 1) {
    const width = points[index + 1].x - points[index].x;
    dx.push(width);
    slopes.push(width === 0 ? 0 : (points[index + 1].y - points[index].y) / width);
  }

  const tangents: number[] = new Array(n).fill(0);
  tangents[0] = slopes[0];
  tangents[n - 1] = slopes[n - 2];
  for (let index = 1; index < n - 1; index += 1) {
    const previous = slopes[index - 1];
    const next = slopes[index];
    if (previous * next <= 0) {
      tangents[index] = 0;
      continue;
    }
    const widthBack = dx[index - 1];
    const widthForward = dx[index];
    const w1 = 2 * widthForward + widthBack;
    const w2 = widthForward + 2 * widthBack;
    tangents[index] = (w1 + w2) / (w1 / previous + w2 / next);
  }

  const clamp = (value: number): number => {
    if (minY !== undefined && maxY !== undefined) {
      return Math.max(minY, Math.min(maxY, value));
    }
    return value;
  };

  let path = `M ${round(points[0].x)} ${round(points[0].y)}`;
  for (let index = 0; index < n - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const c1x = start.x + dx[index] / 3;
    const c1y = clamp(start.y + (tangents[index] * dx[index]) / 3);
    const c2x = end.x - dx[index] / 3;
    const c2y = clamp(end.y - (tangents[index + 1] * dx[index]) / 3);
    path += ` C ${round(c1x)} ${round(c1y)}, ${round(c2x)} ${round(c2y)}, ${round(end.x)} ${round(end.y)}`;
  }
  return path;
}
