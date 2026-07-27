export type LyricLine = {
  index: number;
  text: string;
  start: number;
  end: number;
  isSection: boolean;
};

const LRC_LINE = /^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$/;

function isSectionHeader(text: string): boolean {
  const t = text.trim();
  return /^\[[^\]]+\]$/.test(t) || /^\[.+\]\s*$/.test(t);
}

/** Parse LRC timestamps if present; otherwise return null. */
export function parseLrcLines(raw: string): LyricLine[] | null {
  const lines = raw.split(/\r?\n/);
  const timed: { time: number; text: string }[] = [];
  let hits = 0;
  for (const line of lines) {
    const match = line.match(LRC_LINE);
    if (!match) continue;
    hits += 1;
    const minutes = Number(match[1]);
    const seconds = Number(match[2]);
    const frac = match[3] ? Number(match[3].padEnd(3, '0').slice(0, 3)) / 1000 : 0;
    const text = (match[4] || '').trim();
    timed.push({ time: minutes * 60 + seconds + frac, text });
  }
  if (hits < 2) return null;
  timed.sort((a, b) => a.time - b.time);
  return timed.map((item, index) => ({
    index,
    text: item.text || '♪',
    start: item.time,
    end: timed[index + 1]?.time ?? item.time + 4,
    isSection: isSectionHeader(item.text),
  }));
}

/** Plain (non-LRC) lyric lines for static display — no invented timing. */
export function plainLyricLines(raw: string | null | undefined): LyricLine[] {
  const texts = (raw || '')
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0);

  return texts.map((text, index) => ({
    index,
    text,
    start: 0,
    end: 0,
    isSection: isSectionHeader(text),
  }));
}

export function hasLrcTimestamps(raw: string | null | undefined): boolean {
  return Boolean(parseLrcLines((raw || '').trim()));
}

/**
 * Prefer real LRC timing. Plain lyrics return static lines (no estimated karaoke).
 */
export function buildLyricTimeline(raw: string | null | undefined, _durationSeconds?: number): {
  lines: LyricLine[];
  synced: boolean;
} {
  const text = (raw || '').trim();
  if (!text) return { lines: [], synced: false };
  const lrc = parseLrcLines(text);
  if (lrc) return { lines: lrc, synced: true };
  return { lines: plainLyricLines(text), synced: false };
}

export function activeLyricIndex(lines: LyricLine[], currentTime: number): number {
  if (!lines.length) return -1;
  if (currentTime < lines[0].start) return -1;
  for (let i = 0; i < lines.length; i += 1) {
    if (currentTime >= lines[i].start && currentTime < lines[i].end) return i;
  }
  return lines.length - 1;
}
