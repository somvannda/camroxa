/**
 * LRC / SRT conversion for aligned lyrics.
 *
 * Ported from the legacy `platform_api/services/suno_lrc.py`, which consumed
 * sunoapi.org's `alignedWords`. The active product has no upstream word
 * alignment — we produce it in `musicapi/lrc-service` — but the data shape is
 * deliberately identical, so one typed module owns the text conversion for
 * every surface (`/me/lyrics/:id`, `/v1/lyrics/:id`,
 * `POST /api/v1/generate/get-timestamped-lyrics`).
 */

export interface AlignedWord {
  /** The token. May embed `\n` to mark a line/section break (legacy shape). */
  word: string;
  startS: number;
  endS?: number;
  [key: string]: unknown;
}

/** One timed lyric line, as produced by the aligner. */
export interface AlignedLine {
  text: string;
  startS: number;
  endS?: number;
}

const LRC_LINE = /^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$/;
const LRC_HIT = /^\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]/gm;

function pad(value: number, width: number): string {
  return String(Math.trunc(value)).padStart(width, "0");
}

/** `[mm:ss.xx]`, matching the legacy Python `format_lrc_time`. */
export function formatLrcTime(seconds: number): string {
  const total = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(total / 60);
  const secs = total - minutes * 60;
  return `[${pad(minutes, 2)}:${secs.toFixed(2).padStart(5, "0")}]`;
}

/** Seconds from LRC `mm`, `ss`, and optional fractional `millis`. */
export function parseLrcTimestamp(minutes: string, seconds: string, millis?: string): number {
  let total = parseInt(minutes, 10) * 60 + parseInt(seconds, 10);
  if (millis) {
    if (millis.length === 1) total += parseInt(millis, 10) / 10;
    else if (millis.length === 2) total += parseInt(millis, 10) / 100;
    else total += parseInt(millis.slice(0, 3), 10) / 1000;
  }
  return Math.max(0, total);
}

function wordStart(item: Record<string, unknown>): number {
  for (const key of ["startS", "start_s", "start"]) {
    const raw = item[key];
    if (raw === null || raw === undefined || raw === "") continue;
    const value = Number(raw);
    if (Number.isFinite(value)) return value;
  }
  return 0;
}

function wordText(item: Record<string, unknown>): string {
  const raw = item.word ?? item.text;
  return typeof raw === "string" ? raw : "";
}

/**
 * Group word alignments into line-level LRC.
 *
 * Aligners embed newlines in `word` to mark line/section breaks (e.g.
 * `"Snowflakes\n"`). We flush a line whenever a newline appears and stamp it
 * with the first word's start time. Returns `""` when fewer than two lines
 * survive — a single tag is not usable LRC and the streaming UI treats it as
 * plain text.
 */
export function alignedWordsToLrc(words: AlignedWord[] | null | undefined): string {
  if (!words || words.length === 0) return "";

  const lines: Array<[number, string]> = [];
  let buf: string[] = [];
  let lineStart: number | null = null;

  const flush = (): void => {
    const text = buf.join("").replace(/[ \t]+/g, " ").trim();
    if (text && lineStart !== null) lines.push([lineStart, text]);
    buf = [];
    lineStart = null;
  };

  for (const item of words) {
    if (!item || typeof item !== "object") continue;
    const word = wordText(item);
    if (!word) continue;
    const start = wordStart(item);
    word.split("\n").forEach((part, index) => {
      if (index > 0) flush();
      if (!part) return;
      if (lineStart === null) lineStart = start;
      buf.push(part);
    });
  }
  flush();

  if (lines.length < 2) return "";
  return lines.map(([start, text]) => `${formatLrcTime(start)}${text}`).join("\n");
}

/** Line-level LRC from already-grouped lines (aligner output). */
export function alignedLinesToLrc(lines: AlignedLine[] | null | undefined): string {
  if (!lines || lines.length < 2) return "";
  const rendered = lines
    .filter((line) => line && typeof line.text === "string" && line.text.trim())
    .map((line) => `${formatLrcTime(line.startS)}${line.text.trim()}`);
  return rendered.length >= 2 ? rendered.join("\n") : "";
}

/**
 * Extract the `alignedWords` list from a `get-timestamped-lyrics`-shaped body
 * (`{data:{alignedWords}}`, `{alignedWords}`, or a bare list).
 */
export function parseAlignedWordsPayload(payload: unknown): AlignedWord[] {
  if (!payload || typeof payload !== "object") return [];
  const root = payload as Record<string, unknown>;
  const data =
    root.data && typeof root.data === "object"
      ? (root.data as Record<string, unknown>)
      : root;
  for (const key of ["alignedWords", "aligned_words"]) {
    const words = data[key];
    if (Array.isArray(words)) {
      return words.filter(
        (item): item is AlignedWord => Boolean(item) && typeof item === "object",
      );
    }
  }
  return [];
}

/** Parse line-level LRC into `[startSeconds, text]`. */
export function parseLrcLines(lrc: string): Array<[number, string]> {
  const parsed: Array<[number, string]> = [];
  for (const rawLine of String(lrc ?? "").split("\n")) {
    const match = rawLine.trim().match(LRC_LINE);
    if (!match) continue;
    const [, minutes, seconds, millis, text] = match;
    const cleaned = String(text ?? "").trim();
    if (!cleaned) continue;
    parsed.push([parseLrcTimestamp(minutes, seconds, millis), cleaned]);
  }
  return parsed;
}

/** True when text has at least two LRC timestamp tags. */
export function looksLikeLrc(text: string | null | undefined): boolean {
  if (!text || !String(text).trim()) return false;
  return (String(text).match(LRC_HIT)?.length ?? 0) >= 2;
}

/** `HH:MM:SS,mmm`, matching the legacy Python `format_srt_time`. */
export function formatSrtTime(seconds: number): string {
  const totalMs = Math.max(0, Math.round((Number(seconds) || 0) * 1000));
  const hours = Math.floor(totalMs / 3_600_000);
  const minutes = Math.floor((totalMs % 3_600_000) / 60_000);
  const secs = Math.floor((totalMs % 60_000) / 1000);
  const millis = totalMs % 1000;
  return `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(secs, 2)},${pad(millis, 3)}`;
}

/** Convert line-level LRC into basic SRT cues for video editors. */
export function lrcToSrt(lrc: string): string {
  const entries = parseLrcLines(lrc);
  if (entries.length === 0) return "";
  const blocks: string[] = [];
  entries.forEach(([start, text], index) => {
    const end = index < entries.length - 1 ? Math.max(start + 0.5, entries[index + 1][0] - 0.05) : start + 5;
    blocks.push([String(index + 1), `${formatSrtTime(start)} --> ${formatSrtTime(end)}`, text, ""].join("\n"));
  });
  return blocks.join("\n");
}
