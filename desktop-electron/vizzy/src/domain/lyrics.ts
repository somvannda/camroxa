/**
 * Lyrics/subtitle parsing, ported from the reference's module 624 plus the
 * formats it delegates to (LRC, SRT, WebVTT, TTML, DistroKid JSON, Vizzy JSON).
 */

export interface LyricLine {
  start: number;
  end: number;
  text: string;
}

function parseTimestamp(value: string): number {
  const parts = value.trim().replace(",", ".").split(":");
  let seconds = 0;
  let minutes = 0;
  let hours = 0;
  if (parts.length === 3) {
    hours = parseFloat(parts[0]);
    minutes = parseFloat(parts[1]);
    seconds = parseFloat(parts[2]);
  } else if (parts.length === 2) {
    minutes = parseFloat(parts[0]);
    seconds = parseFloat(parts[1]);
  } else {
    return parseFloat(value);
  }
  return hours * 3600 + minutes * 60 + seconds;
}

function isVizzyLine(value: unknown): value is { start: number; end?: number; text: string } {
  if (!value || typeof value !== "object") return false;
  const line = value as { start?: unknown; end?: unknown; text?: unknown };
  return (
    typeof line.start === "number" &&
    (typeof line.end === "number" || line.end === undefined) &&
    typeof line.text === "string"
  );
}

function parseJson(text: string): LyricLine[] | null {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object") return null;
  const distro = value as { timed?: { line?: Array<{ begin?: number; end?: number; content?: string }> } };
  if (distro.timed && Array.isArray(distro.timed.line)) {
    return distro.timed.line.map((line) => ({
      start: Number(line.begin ?? 0),
      end: Number(line.end ?? Number(line.begin ?? 0) + 1),
      text: String(line.content ?? ""),
    }));
  }
  if (Array.isArray(value)) {
    const flat = value.length > 0 && Array.isArray(value[0]) ? (value as unknown[]).flat() : value;
    if (flat.every(isVizzyLine)) {
      return (flat as Array<{ start: number; end?: number; text: string }>).map((line) => ({
        start: line.start,
        end: line.end ?? line.start + 1,
        text: line.text,
      }));
    }
  }
  return null;
}

function stripMarkup(text: string): string {
  return text
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function parseTtml(text: string): LyricLine[] | null {
  if (!text.startsWith("<?xml") && !text.includes("<tt xmlns")) return null;
  const lines: LyricLine[] = [];
  const pattern = /<p\b([^>]*)>([\s\S]*?)<\/p>/gi;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    const attrs = match[1];
    const begin = /\bbegin\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    const end = /\bend\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    if (!begin || !end) continue;
    lines.push({ start: parseTimestamp(begin), end: parseTimestamp(end), text: stripMarkup(match[2]).trim() });
  }
  return lines.length ? lines : null;
}

function parseCues(text: string): LyricLine[] | null {
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const blocks = normalized.split(/\n{2,}/);
  const lines: LyricLine[] = [];
  for (const block of blocks) {
    const rows = block.split("\n").filter((row) => row.trim() !== "");
    const timingIndex = rows.findIndex((row) => row.includes("-->"));
    if (timingIndex < 0) continue;
    const timing = rows[timingIndex];
    const match = /(\d{1,2}:\d{2}(?::\d{2})?[.,]\d+)\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?[.,]\d+)/.exec(timing);
    if (!match) continue;
    const textRows = rows.slice(timingIndex + 1).join("\n");
    lines.push({
      start: parseTimestamp(match[1]),
      end: parseTimestamp(match[2]),
      text: stripMarkup(textRows).trim(),
    });
  }
  return lines.length ? lines : null;
}

function parseLrc(text: string): LyricLine[] | null {
  const rows = text.split(/\r?\n/);
  const timed: Array<{ time: number; text: string }> = [];
  const offsetMatch = /^\[offset:([+-]?\d+)\]/i.exec(text);
  const offset = offsetMatch ? Number(offsetMatch[1]) / 1000 : 0;
  for (const row of rows) {
    const stamps = [...row.matchAll(/\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g)];
    if (!stamps.length) continue;
    const body = row.replace(/\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g, "").trim();
    for (const stamp of stamps) {
      const minutes = Number(stamp[1]);
      const seconds = Number(stamp[2]);
      const fraction = stamp[3] ? Number(`0.${stamp[3]}`) : 0;
      timed.push({ time: minutes * 60 + seconds + fraction + offset, text: body });
    }
  }
  if (!timed.length) return null;
  timed.sort((a, b) => a.time - b.time);
  return timed.map((line, index) => ({
    start: line.time,
    end: timed[index + 1]?.time ?? line.time + 4,
    text: line.text,
  }));
}

/** Parses any lyrics/subtitle format the reference accepts. */
export function parseLyrics(input: string): LyricLine[] {
  if (!input || typeof input !== "string") {
    throw new Error("Invalid content provided for lyrics parsing");
  }
  const text = input.trim();
  const json = parseJson(text);
  if (json) return json;
  const ttml = parseTtml(text);
  if (ttml) return ttml;
  if (/^WEBVTT/i.test(text)) {
    const cues = parseCues(text);
    if (cues) return cues;
  }
  if (/\[[0-9]{2}:[0-9]{2}(\.[0-9]{2,3})?\]/.test(text)) {
    const lrc = parseLrc(text);
    if (lrc) return lrc;
  }
  const cues = parseCues(text);
  if (cues) return cues;
  throw new Error("Could not determine lyrics format");
}
