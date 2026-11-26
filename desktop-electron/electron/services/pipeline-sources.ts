/**
 * Run-audio resolution for the video pipeline.
 *
 * The Music page knows the run folders the backend recorded
 * (`output_dir_ok` / `output_dir_alt`) but not the audio file names: Suno
 * downloads are named after the song (`1. Title.mp3`, `1. Title_Alt.mp3`).
 * This module resolves a song title to an audio file inside its run folder,
 * and refuses to guess when the match is ambiguous. Pure Node, no Electron.
 */
import fs from "node:fs";
import path from "node:path";

export const AUDIO_EXTENSIONS = [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"] as const;

export type AudioBranch = "ok" | "alt";

export type AudioLookup =
  | { ok: true; path: string; name: string }
  | { ok: false; reason: string };

/** `"2. Echoes in Empty Rooms_Alt"` → `"echoes in empty rooms"`. */
export function normaliseSongName(value: string): string {
  return value
    .replace(/\.[a-z0-9]{2,5}$/i, "")
    .replace(/^\s*\d+\s*[.)\-–]?\s*/, "")
    .replace(/[_\s-]+(alt|ok)\s*$/i, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function isAudioFile(name: string): boolean {
  return (AUDIO_EXTENSIONS as readonly string[]).includes(path.extname(name).toLowerCase());
}

/** Absolute audio file paths in a folder, sorted for determinism. */
export function listAudioFiles(dir: string): string[] {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  return entries
    .filter((entry) => entry.isFile() && isAudioFile(entry.name))
    .map((entry) => path.join(dir, entry.name))
    .sort((left, right) => left.localeCompare(right));
}

function isAltFile(name: string): boolean {
  return /(?:^|[_\s-])alt(?:\.[a-z0-9]{2,5})?$/i.test(name);
}

/**
 * Resolve one song's audio inside its run folder.
 *
 * Order: exact normalised name → contained name → a single unambiguous file.
 * `allowOnlyFile` lets a single-track folder answer even when the stored title
 * no longer matches (the user renamed the track); it is never used when the
 * folder holds more than one candidate.
 */
export function findAudioForSong(
  dir: string,
  title: string,
  branch: AudioBranch = "ok",
  options: { allowOnlyFile?: boolean; trackIndex?: number } = {},
): AudioLookup {
  const resolved = dir?.trim();
  if (!resolved) return { ok: false, reason: "The run folder is not set." };
  let stat: fs.Stats;
  try {
    stat = fs.statSync(resolved);
  } catch {
    return { ok: false, reason: `The run folder does not exist: ${resolved}` };
  }
  if (!stat.isDirectory()) return { ok: false, reason: "The run path is not a folder." };

  const files = listAudioFiles(resolved);
  if (files.length === 0) return { ok: false, reason: "No audio files in the run folder yet." };

  const branchMatches = files.filter((file) => isAltFile(file) === (branch === "alt"));
  const pool = branchMatches.length > 0 ? branchMatches : files;
  const target = normaliseSongName(title);

  // Suno names downloads after the track (`3. Pulse Divide_OK.mp3`). Two songs
  // can share a title, so the track number decides before the title does.
  const trackIndex = Number(options.trackIndex ?? 0);
  if (Number.isInteger(trackIndex) && trackIndex > 0) {
    const prefix = new RegExp(`^\\s*${trackIndex}\\s*[.)\\-–]?\\s`);
    const byTrack = pool.filter((file) => prefix.test(path.basename(file)));
    if (byTrack.length === 1) return toLookup(byTrack[0]);
    if (byTrack.length > 1 && target) {
      const exactByTrack = byTrack.filter(
        (file) => normaliseSongName(path.basename(file)) === target,
      );
      if (exactByTrack.length === 1) return toLookup(exactByTrack[0]);
    }
  }

  if (target) {
    const exact = pool.filter((file) => normaliseSongName(path.basename(file)) === target);
    if (exact.length === 1) return toLookup(exact[0]);
    if (exact.length > 1) {
      return { ok: false, reason: `More than one audio file matches "${title}".` };
    }
    const contained = pool.filter((file) => {
      const name = normaliseSongName(path.basename(file));
      return (
        name.length > 0 &&
        target.length >= 4 &&
        (name.includes(target) || target.includes(name))
      );
    });
    if (contained.length === 1) return toLookup(contained[0]);
    if (contained.length > 1) {
      return { ok: false, reason: `More than one audio file matches "${title}".` };
    }
  }

  if (options.allowOnlyFile && pool.length === 1) return toLookup(pool[0]);
  if (!target) {
    return { ok: false, reason: "The song has no title to match its audio against." };
  }
  return { ok: false, reason: `No audio file matches "${title}" in the run folder.` };
}

function toLookup(filePath: string): AudioLookup {
  try {
    const stat = fs.statSync(filePath);
    if (!stat.isFile() || stat.size <= 0) {
      return { ok: false, reason: `The audio file is empty: ${path.basename(filePath)}` };
    }
  } catch {
    return { ok: false, reason: `The audio file disappeared: ${path.basename(filePath)}` };
  }
  return { ok: true, path: filePath, name: path.basename(filePath) };
}

/** First free `<stem>.mp4` in `dir` (never overwrites an existing merge). */
export function uniqueOutputPath(dir: string, stem: string): string {
  const base = (stem || "merged").replace(/[\\/:*?"<>|]+/g, "-").replace(/\.(mp4|webm)$/i, "").trim();
  const safeBase = base || "merged";
  const resolved = path.resolve(dir, `${safeBase}.mp4`);
  if (!fs.existsSync(resolved)) return resolved;
  for (let index = 1; index < 100; index += 1) {
    const candidate = path.resolve(dir, `${safeBase} (${index}).mp4`);
    if (!fs.existsSync(candidate)) return candidate;
  }
  return resolved;
}
