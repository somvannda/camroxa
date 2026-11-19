export function parseProgressLine(line: string): { key: string; value: string } | null {
  const index = line.indexOf("=");
  if (index <= 0) return null;
  return { key: line.slice(0, index).trim(), value: line.slice(index + 1).trim() };
}

export function progressPercent(timeMs: number, durationSec: number | undefined): number {
  if (!durationSec || durationSec <= 0) return 0;
  return Math.max(0, Math.min(100, (timeMs / 1000 / durationSec) * 100));
}
