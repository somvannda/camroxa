import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  findAudioForSong,
  listAudioFiles,
  normaliseSongName,
  uniqueOutputPath,
} from "../../electron/services/pipeline-sources";

let root: string;

beforeAll(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-pipeline-sources-"));
});

afterAll(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

function folder(name: string, files: string[]): string {
  const dir = path.join(root, name);
  fs.mkdirSync(dir, { recursive: true });
  for (const file of files) fs.writeFileSync(path.join(dir, file), "audio-bytes");
  return dir;
}

describe("pipeline sources", () => {
  it("normalises the Suno download naming convention", () => {
    expect(normaliseSongName("2. Echoes in Empty Rooms_Alt.mp3")).toBe("echoes in empty rooms");
    expect(normaliseSongName("01 - Night Drive.mp3")).toBe("night drive");
    expect(normaliseSongName("Track_Ok.wav")).toBe("track");
    expect(normaliseSongName("Trap Motion")).toBe("trap motion");
  });

  it("lists only audio files, sorted", () => {
    const dir = folder("list", ["b.mp3", "a.wav", "cover.png", "notes.txt"]);
    expect(listAudioFiles(dir).map((file) => path.basename(file))).toEqual(["a.wav", "b.mp3"]);
  });

  it("resolves the exact song and respects the alt branch", () => {
    const dir = folder("pair", ["1. Night Drive.mp3", "1. Night Drive_Alt.mp3"]);
    const ok = findAudioForSong(dir, "Night Drive", "ok");
    expect(ok.ok).toBe(true);
    if (ok.ok) expect(path.basename(ok.path)).toBe("1. Night Drive.mp3");

    const alt = findAudioForSong(dir, "Night Drive", "alt");
    expect(alt.ok).toBe(true);
    if (alt.ok) expect(path.basename(alt.path)).toBe("1. Night Drive_Alt.mp3");
  });

  it("refuses to guess between two candidates", () => {
    const dir = folder("ambiguous", ["Night Drive.mp3", "Night Drive Live.mp3"]);
    const found = findAudioForSong(dir, "Night Drive", "ok");
    // "night drive" is an exact match on the first file only, so it resolves.
    expect(found.ok).toBe(true);
    if (found.ok) expect(path.basename(found.path)).toBe("Night Drive.mp3");

    const other = folder("ambiguous-2", ["Night Drive.mp3", "Night-Drive.mp3"]);
    const both = findAudioForSong(other, "Night Drive", "ok");
    expect(both.ok).toBe(false);
    if (!both.ok) expect(both.reason).toMatch(/more than one/i);
  });

  it("falls back to the only file when the title changed", () => {
    const dir = folder("renamed", ["01 - Old Working Title.mp3"]);
    const strict = findAudioForSong(dir, "Brand New Title", "ok");
    expect(strict.ok).toBe(false);
    const relaxed = findAudioForSong(dir, "Brand New Title", "ok", { allowOnlyFile: true });
    expect(relaxed.ok).toBe(true);
  });

  it("reports a missing folder, empty folder and empty file", () => {
    expect(findAudioForSong(path.join(root, "nope"), "Song").ok).toBe(false);
    const empty = folder("empty", []);
    const missing = findAudioForSong(empty, "Song");
    expect(missing.ok).toBe(false);
    if (!missing.ok) expect(missing.reason).toMatch(/no audio files/i);

    const blank = folder("blank", ["Song.mp3"]);
    fs.writeFileSync(path.join(blank, "Song.mp3"), "");
    const zero = findAudioForSong(blank, "Song");
    expect(zero.ok).toBe(false);
    if (!zero.ok) expect(zero.reason).toMatch(/empty/i);
  });

  it("never overwrites an existing merged file", () => {
    const dir = folder("out", ["batch-merged.mp4"]);
    expect(path.basename(uniqueOutputPath(dir, "batch-merged"))).toBe("batch-merged-2.mp4");
  });
});
