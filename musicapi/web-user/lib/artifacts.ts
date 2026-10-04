/**
 * Result-artifact helpers for the usage logs.
 *
 * A single generation endpoint can produce very different things — audio clips,
 * an MP4 render, raw MIDI note events, aligned lyric text, or a voice persona —
 * so the logs UI cannot assume every row is a downloadable music clip. This
 * module turns a stored `result_json` (plus its endpoint) into a typed artifact
 * that the UI can render appropriately, and provides the small client-side
 * exporters (Standard MIDI File, LRC→SRT, plain blob downloads) that replace
 * the old "everything is an MP3/WAV" assumption.
 */

export interface LogClip {
  id: string;
  audioUrl: string | null;
}

export interface MidiNote {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
}

export interface MidiInstrument {
  name: string;
  notes: MidiNote[];
}

export interface TextAsset {
  /** Short button label, e.g. "LRC" / "SRT" / "Lyrics". */
  label: string;
  filename: string;
  content: string;
  mime: string;
}

export type Artifact =
  | { kind: "audio"; clips: LogClip[] }
  | { kind: "video"; videoUrl: string | null; clipId: string | null }
  | { kind: "midi"; instruments: MidiInstrument[]; audioId: string | null }
  | { kind: "text"; assets: TextAsset[] }
  | { kind: "persona"; fields: Array<{ label: string; value: string }> }
  | { kind: "image"; imageUrl: string }
  | { kind: "raw" };

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function mediaUrlOf(rec: Record<string, unknown>): string | null {
  const media = Array.isArray(rec.media_urls) ? rec.media_urls[0] : null;
  const mediaUrl = asRecord(media)?.url;
  return str(mediaUrl) ?? str(rec.audio_url) ?? str(rec.audioUrl) ?? str(rec.url);
}

/**
 * Collect playable audio clips from a result of any known shape:
 * `clips`/`items`/`data` arrays (music generation) and `tracks` (recovery
 * audio, whose entries are `{id, audio_url, ...}` rather than clips).
 */
export function extractClipList(result: unknown): LogClip[] {
  const list: unknown[] = [];
  if (Array.isArray(result)) {
    list.push(...result);
  } else {
    const rec = asRecord(result);
    if (rec) {
      for (const key of ["clips", "items", "data", "tracks"]) {
        const arr = rec[key];
        if (Array.isArray(arr)) list.push(...arr);
      }
    }
  }
  const out: LogClip[] = [];
  for (const c of list) {
    const rec = asRecord(c);
    if (!rec || typeof rec.id !== "string" || !rec.id) continue;
    out.push({ id: rec.id, audioUrl: mediaUrlOf(rec) });
  }
  return out;
}

function pickVideoUrl(rec: Record<string, unknown> | null): string | null {
  if (!rec) return null;
  const direct = str(rec.video_url) ?? str(rec.videoUrl);
  if (direct) return direct;
  const download = str(rec.download_url);
  if (download && /\.mp4(\?|$)/i.test(download)) return download;
  return null;
}

function parseLrcTag(tag: string): number {
  const m = tag.match(/(\d+):(\d+)(?:[.:](\d+))?/);
  if (!m) return 0;
  const min = Number(m[1]);
  const sec = Number(m[2]);
  const frac = m[3] ? Number(`0.${m[3]}`) : 0;
  return min * 60 + sec + frac;
}

function srtTime(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = Math.floor(clamped % 60);
  const ms = Math.round((clamped - Math.floor(clamped)) * 1000);
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
}

interface TimedLine {
  start: number;
  end?: number;
  text: string;
}

function linesToSrt(lines: TimedLine[]): string {
  const sorted = [...lines].sort((a, b) => a.start - b.start);
  let out = "";
  sorted.forEach((line, i) => {
    const end = line.end ?? sorted[i + 1]?.start ?? line.start + 2;
    out += `${i + 1}\n${srtTime(line.start)} --> ${srtTime(Math.max(line.start, end))}\n${line.text}\n\n`;
  });
  return out.trim() ? `${out.trim()}\n` : "";
}

/** Convert an LRC timing track (`[mm:ss.xx]text`) into SRT subtitles. */
export function lrcToSrt(lrc: string): string {
  const entries: Array<{ start: number; text: string }> = [];
  for (const raw of lrc.split(/\r?\n/)) {
    const tags = raw.match(/\[(\d+:\d+(?:[.:]\d+)?)\]/g) ?? [];
    const text = raw.replace(/\[[^\]]*\]/g, "").trim();
    if (tags.length === 0 || !text) continue;
    for (const tag of tags) entries.push({ start: parseLrcTag(tag.replace(/[[\]]/g, "")), text });
  }
  return linesToSrt(entries.map((e) => ({ start: e.start, text: e.text })));
}

function alignedLinesToSrt(lines: unknown): string {
  const parsed: TimedLine[] = [];
  if (!Array.isArray(lines)) return "";
  for (const line of lines) {
    if (!line || typeof line !== "object") continue;
    const rec = line as Record<string, unknown>;
    const start = Number(rec.start);
    const end = rec.end != null ? Number(rec.end) : undefined;
    const text = str(rec.text) ?? str(rec.lyric);
    if (!Number.isFinite(start) || !text) continue;
    parsed.push({ start, end: Number.isFinite(end) ? end : undefined, text });
  }
  return linesToSrt(parsed);
}

function extractTextAssets(rec: Record<string, unknown> | null): TextAsset[] {
  if (!rec) return [];
  const assets: TextAsset[] = [];
  const lrc = str(rec.lrc);
  const subtitle = str(rec.subtitle);
  const lyrics = str(rec.lyrics);
  if (lrc) assets.push({ label: "LRC", filename: "lyrics.lrc", content: lrc, mime: "text/plain" });
  if (subtitle) {
    assets.push({ label: "SRT", filename: "subtitle.srt", content: subtitle, mime: "text/plain" });
  } else if (lrc) {
    assets.push({ label: "SRT", filename: "subtitle.srt", content: lrcToSrt(lrc), mime: "text/plain" });
  } else {
    const srt = alignedLinesToSrt(rec.aligned_lines);
    if (srt) assets.push({ label: "SRT", filename: "subtitle.srt", content: srt, mime: "text/plain" });
  }
  if (lyrics) assets.push({ label: "Lyrics", filename: "lyrics.txt", content: lyrics, mime: "text/plain" });
  return assets;
}

function normalizeInstruments(value: unknown): MidiInstrument[] {
  if (!Array.isArray(value)) return [];
  const out: MidiInstrument[] = [];
  for (const inst of value) {
    const rec = asRecord(inst);
    if (!rec) continue;
    const notes: MidiNote[] = [];
    if (Array.isArray(rec.notes)) {
      for (const n of rec.notes) {
        const note = asRecord(n);
        if (!note) continue;
        const pitch = Number(note.pitch);
        const start = Number(note.start);
        const end = Number(note.end);
        const velocity = Number(note.velocity);
        if (!Number.isFinite(pitch) || !Number.isFinite(start)) continue;
        notes.push({
          pitch,
          start,
          end: Number.isFinite(end) ? end : start + 0.25,
          velocity: Number.isFinite(velocity) ? velocity : 0.8,
        });
      }
    }
    out.push({ name: str(rec.name) ?? "Instrument", notes });
  }
  return out;
}

function personaFields(rec: Record<string, unknown>): Array<{ label: string; value: string }> {
  const candidates: Array<[string, unknown]> = [
    ["persona_id", rec.persona_id],
    ["id", rec.id],
    ["name", rec.name],
    ["voice_id", rec.voice_id],
    ["description", rec.description],
    ["status", rec.status],
  ];
  const fields: Array<{ label: string; value: string }> = [];
  for (const [label, value] of candidates) {
    const s = str(value);
    if (s) fields.push({ label, value: s });
  }
  return fields;
}

/**
 * Classify a stored result into a renderable artifact. Endpoint-aware where the
 * shape alone is ambiguous (e.g. a detail-route clip record vs. a video result).
 */
export function classifyResult(result: unknown, endpoint = ""): Artifact {
  const ep = (endpoint || "").toLowerCase();
  const rec = asRecord(result);

  // 1. Audio clip lists win whenever present — music, cover, stems, voice
  //    apply/extend all return clips (or recovery `tracks`).
  const clips = extractClipList(result);
  if (clips.length > 0) return { kind: "audio", clips };

  // 2. MIDI generation — raw note events, no audio exists.
  const midi = rec?.midi_data;
  if (midi && typeof midi === "object") {
    return {
      kind: "midi",
      instruments: normalizeInstruments((midi as Record<string, unknown>).instruments),
      audioId: str(rec?.audio_id) ?? str(rec?.source_task_id),
    };
  }

  // 3. Video / MP4.
  const videoUrl = pickVideoUrl(rec);
  if (videoUrl) return { kind: "video", videoUrl, clipId: str(rec?.clip_id) ?? str(rec?.id) };

  // 4. Text assets — timestamped lyrics, subtitles, plain lyrics.
  const assets = extractTextAssets(rec);
  if (assets.length > 0) return { kind: "text", assets };

  // 5. Voice persona — `/voice-generate` creates a persona, not audio.
  if (/voice|persona/.test(ep) && rec) return { kind: "persona", fields: personaFields(rec) };

  // 6. A lone clip record (detail routes) or a WAV detail envelope.
  if (rec && typeof rec.id === "string" && mediaUrlOf(rec)) {
    return { kind: "audio", clips: [{ id: rec.id, audioUrl: mediaUrlOf(rec) }] };
  }
  if (rec && typeof rec.clip_id === "string" && typeof rec.download_url === "string") {
    return { kind: "audio", clips: [{ id: rec.clip_id, audioUrl: rec.download_url }] };
  }

  // 7. Cover image only.
  const imageUrl = str(rec?.image_url) ?? str(rec?.image_large_url) ?? str(rec?.cover_url);
  if (imageUrl) return { kind: "image", imageUrl };

  return { kind: "raw" };
}

// --- Standard MIDI File (SMF) encoder -------------------------------------
// Basic Pitch emits `{pitch, start, end, velocity}` with times in seconds. A
// fixed 120 BPM / 480 PPQ clock with an explicit tempo meta event keeps the
// rendered .mid faithful to the transcribed timing without a MIDI library.

const PPQ = 480;
const TEMPO_US = 500_000; // 120 BPM

function secondsToTicks(seconds: number): number {
  return Math.max(0, Math.round(seconds * PPQ * 2));
}

function vlq(value: number): number[] {
  let v = Math.max(0, Math.floor(value));
  const bytes = [v & 0x7f];
  v >>= 7;
  while (v > 0) {
    bytes.unshift((v & 0x7f) | 0x80);
    v >>= 7;
  }
  return bytes;
}

function textBytes(text: string): number[] {
  if (typeof TextEncoder !== "undefined") return Array.from(new TextEncoder().encode(text));
  return Array.from(text, (c) => c.charCodeAt(0) & 0xff);
}

function trackChunk(events: Array<{ tick: number; data: number[] }>): number[] {
  const sorted = [...events].sort((a, b) => a.tick - b.tick);
  const body: number[] = [];
  let last = 0;
  for (const e of sorted) {
    body.push(...vlq(e.tick - last), ...e.data);
    last = e.tick;
  }
  body.push(0x00, 0xff, 0x2f, 0x00); // end of track
  const len = body.length;
  return [
    0x4d, 0x54, 0x72, 0x6b,
    (len >>> 24) & 0xff, (len >>> 16) & 0xff, (len >>> 8) & 0xff, len & 0xff,
    ...body,
  ];
}

/** Encode transcribed instruments into a Format-1 Standard MIDI File. */
export function buildMidiFile(instruments: MidiInstrument[]): Uint8Array {
  const tracks: number[][] = [];
  // Track 0: tempo.
  tracks.push(trackChunk([{ tick: 0, data: [0xff, 0x51, 0x03, (TEMPO_US >> 16) & 0xff, (TEMPO_US >> 8) & 0xff, TEMPO_US & 0xff] }]));

  for (const inst of instruments) {
    const events: Array<{ tick: number; data: number[] }> = [];
    const name = textBytes(inst.name || "Instrument").slice(0, 120);
    events.push({ tick: 0, data: [0xff, 0x03, name.length, ...name] });
    for (const note of inst.notes) {
      const start = secondsToTicks(note.start);
      const end = Math.max(start + 1, secondsToTicks(note.end));
      const pitch = Math.max(0, Math.min(127, Math.round(note.pitch)));
      const velocity = Math.max(1, Math.min(127, Math.round((note.velocity || 0.8) * 127)));
      events.push({ tick: start, data: [0x90, pitch, velocity] });
      events.push({ tick: end, data: [0x80, pitch, 0x40] });
    }
    tracks.push(trackChunk(events));
  }

  const header = [
    0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6,
    0, 1, // format 1
    (tracks.length >> 8) & 0xff, tracks.length & 0xff,
    (PPQ >> 8) & 0xff, PPQ & 0xff,
  ];
  const out: number[] = [...header];
  for (const track of tracks) out.push(...track);
  return new Uint8Array(out);
}

/** Trigger a browser download for in-memory bytes or text (no server round-trip). */
export function downloadBytes(filename: string, data: Uint8Array | string, mime: string): void {
  const blob = new Blob([data as BlobPart], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
