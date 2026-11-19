import path from "node:path";
import { describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";
import { getDevicePreferences, setDevicePreferences } from "../../electron/services/device-settings";

function store() {
  const db = createDatabase(":memory:");
  return db;
}

describe("device preferences", () => {
  it("starts empty", () => {
    const db = store();
    expect(getDevicePreferences(db)).toEqual({ ffmpegPath: "", sunoOutputDir: "" });
    db.close();
  });

  it("stores absolute paths and trims whitespace", () => {
    const db = store();
    const ffmpeg = path.resolve("tools", "ffmpeg.exe");
    const suno = path.resolve("output");
    expect(setDevicePreferences({ ffmpegPath: `  ${ffmpeg}  `, sunoOutputDir: suno }, db)).toEqual({
      ffmpegPath: ffmpeg,
      sunoOutputDir: suno,
    });
    expect(getDevicePreferences(db).ffmpegPath).toBe(ffmpeg);
    db.close();
  });

  it("rejects relative paths", () => {
    const db = store();
    expect(() => setDevicePreferences({ ffmpegPath: "tools/ffmpeg.exe" }, db)).toThrow(
      /absolute path/i,
    );
    expect(() => setDevicePreferences({ sunoOutputDir: "output" }, db)).toThrow(/absolute path/i);
    db.close();
  });

  it("allows clearing a path", () => {
    const db = store();
    setDevicePreferences({ sunoOutputDir: path.resolve("output") }, db);
    expect(setDevicePreferences({ sunoOutputDir: "" }, db).sunoOutputDir).toBe("");
    db.close();
  });
});
