import path from "node:path";
import type { DevicePreferences } from "../shared/types";
import { getStore } from "./store";
import type { Store } from "./database";

const FFMPEG_KEY = "device.ffmpegPath";
const SUNO_KEY = "device.sunoOutputDir";

function storeOrDefault(store?: Store): Store | null {
  if (store) return store;
  try {
    return getStore();
  } catch {
    return null;
  }
}

export function getDevicePreferences(store?: Store): DevicePreferences {
  const db = storeOrDefault(store);
  if (!db) return { ffmpegPath: "", sunoOutputDir: "" };
  return {
    ffmpegPath: db.getMeta(FFMPEG_KEY) ?? "",
    sunoOutputDir: db.getMeta(SUNO_KEY) ?? "",
  };
}

export function setDevicePreferences(
  input: Partial<DevicePreferences>,
  store?: Store,
): DevicePreferences {
  const db = storeOrDefault(store);
  if (!db) throw new Error("The local settings store is not ready.");
  if (input.ffmpegPath !== undefined) {
    const value = input.ffmpegPath.trim();
    if (value && !path.isAbsolute(value)) {
      throw new Error("The FFmpeg path must be an absolute path.");
    }
    db.setMeta(FFMPEG_KEY, value);
  }
  if (input.sunoOutputDir !== undefined) {
    const value = input.sunoOutputDir.trim();
    if (value && !path.isAbsolute(value)) {
      throw new Error("The Suno output folder must be an absolute path.");
    }
    db.setMeta(SUNO_KEY, value);
  }
  return getDevicePreferences(db);
}
