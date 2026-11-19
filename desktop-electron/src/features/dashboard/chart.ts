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
): string {
  const max = Math.max(0, ...values);
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
