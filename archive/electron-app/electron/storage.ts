import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import type { AppData } from "../shared/app-types";

const DATA_FILE_NAME = "mg-data.json";
const SETTINGS_FILE_NAME = "settings.json";
const LEGACY_SETTINGS_FILE_NAME = "mg-settings.json";

function nowIso() {
  return new Date().toISOString();
}

export function createDefaultData(): AppData {
  const updatedAt = nowIso();
  return {
    descriptions: [
      {
        id: "desc-01",
        name: "01",
        content:
          "High-energy Eurodance and Hands Up track featuring a blend of English vocals. The song is set in a minor key at 142 BPM. It opens with a heavy four-on-the-floor kick drum and a syncopated, buzzy synth bassline.",
        updatedAt,
      },
    ],
    structures: [
      {
        id: "struct-01",
        name: "Festival",
        content:
          "[Intro: kick + hi-hat groove, DJ friendly]\n[Groove: bassline enters, simple rhythm]\n[Build: add percussion layers]\n[Drop: full groove, catchy bassline hook]\n[Break: remove drums, filtered elements]\n[Build: reintroduce rhythm]\n[Drop: same groove with variation]\n[Outro: strip back for mixing]",
        updatedAt,
      },
    ],
    songs: [],
    songDrafts: [
      { id: "draft-01", title: "", album: "" },
    ],
    profiles: [],
    carModels: [],
    imageSamples: [],
    promptTemplates: [],
    textStyles: [],
    history: [],
    settings: {
      language: "English",
      creativity: 55,
      sort: 1,
      template: "Default",
      activeProfileId: null,
      activeProfileOkId: null,
      activeProfileAltId: null,
      channelOkProfileIds: [],
      channelAltProfileIds: [],
      activeDescriptionIds: [],
      activeStructureIds: [],
      matchDescriptionStructure: false,
      showLatest: true,
      shuffle: false,
      shuffleDescription: false,
      shuffleStructure: false,
      enabledDescriptionIds: [],
      enabledStructureIds: [],
      uniqueOpening: false,
      strictLevel: 3,
      uniquenessHistoryWindow: 100,
      cycleStructures: false,
      mergeChunkSize: 7,
      songDraftProvider: "deepseek",
      deepseekApiKey: "",
      openaiApiKey: "",
      slaiSongApiKey: "",
      slaiSongModel: "gpt-5.5",
      slaiImgApiKey: "",
      slaiImgModel: "cgpt-web/gpt-5.5-pro",
      ffmpegPath: "",
      pythonPath: "",
      downloadsDir: "D:\\MusicGenerator\\downloads",
      mergedDir: "D:\\MusicGenerator\\merged",
      defaultSongCount: 1,
      imageOutputDir: "D:\\MusicGenerator\\images",
      imageResolution: "1920x1080",
      styleStrength: 60,
      backgroundSourceMode: "samples",
      thumbnailOverlayMode: "ai",
      backgroundTemplateCycleIndex: 0,
      imageSamplesDir: "",
      videoMergeDirectories: [],
      videoExport: { resolution: "1920x1080", fps: 30, codec: "h264", preset: "fast", crf: 20, audioBitrateKbps: 192 },
      videoRenderOutputDir: "D:\\MusicGenerator\\videos",
      videoRenderTemplatePath: "",
      videoRenderBackgroundPath: "",
      autoGenSongs: true,
      autoGenImage: true,
      autoGSuno: false,
      sunoTimeoutMs: 90000,
      sunoRetryCount: 3,
      sunoDefaultVersion: "v5.5",
      sunoMergeEnabled: false,
      sunoMergeGroupSize: 5,
      sunoApiKey: "",
      sunoOutputDir: "D:\\MusicGenerator\\downloads\\suno",
      sunoCallbackUrl: "https://api.example.com/callback",
      dbHost: "localhost",
      dbPort: 5432,
      dbUser: "postgres",
      dbPassword: "postgres",
      dbName: "MG",
    },
  };
}

export function getDataFilePath(userDataDir: string) {
  return path.join(userDataDir, DATA_FILE_NAME);
}

export function getSettingsFilePath(userDataDir: string) {
  return path.join(userDataDir, SETTINGS_FILE_NAME);
}

function getLegacySettingsFilePath(userDataDir: string) {
  return path.join(userDataDir, LEGACY_SETTINGS_FILE_NAME);
}

async function readSettings(settingsFilePath: string): Promise<AppData["settings"] | null> {
  try {
    const raw = await fs.readFile(settingsFilePath, "utf-8");
    return JSON.parse(raw) as AppData["settings"];
  } catch {
    return null;
  }
}

async function writeSettings(settingsFilePath: string, settings: AppData["settings"]) {
  await writeJsonAtomically(settingsFilePath, settings);
}

async function readBestSettings(settingsFilePath: string, legacySettingsFilePath: string) {
  const settings = await readSettings(settingsFilePath);
  if (settings) return settings;
  const legacy = await readSettings(legacySettingsFilePath);
  if (legacy) {
    await writeSettings(settingsFilePath, legacy);
    return legacy;
  }
  return null;
}

async function writeJsonAtomically(filePath: string, data: unknown) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(data, null, 2), "utf-8");
  for (let i = 0; i < 12; i += 1) {
    try {
      await fs.rename(tmp, filePath);
      return;
    } catch (e) {
      const code = (e as { code?: string })?.code;
      const retryable = code === "EPERM" || code === "EBUSY" || code === "EACCES";
      if (!retryable) throw e;
      await new Promise((r) => setTimeout(r, 35 * (i + 1)));
    }
  }
  await fs.rename(tmp, filePath);
}

let writeChain: Promise<void> = Promise.resolve();

function stamp() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${yyyy}${mm}${dd}-${hh}${mi}${ss}`;
}

export async function readAppData(dataFilePath: string): Promise<AppData> {
  const userDataDir = path.dirname(dataFilePath);
  const settingsFilePath = getSettingsFilePath(userDataDir);
  const legacySettingsFilePath = getLegacySettingsFilePath(userDataDir);
  try {
    const raw = await fs.readFile(dataFilePath, "utf-8");
    let parsed: AppData;
    try {
      parsed = JSON.parse(raw) as AppData;
    } catch {
      const backupPath = path.join(userDataDir, `mg-data.corrupt.${stamp()}.json`);
      await fs.writeFile(backupPath, raw, "utf-8");
      const bestSettings = await readBestSettings(settingsFilePath, legacySettingsFilePath);
      const initial = bestSettings ? { ...createDefaultData(), settings: bestSettings } : createDefaultData();
      await writeAppData(dataFilePath, initial);
      return initial;
    }
    const settings = await readSettings(settingsFilePath);
    if (settings) return { ...parsed, settings };

    const legacy = await readSettings(legacySettingsFilePath);
    if (legacy) {
      await writeSettings(settingsFilePath, legacy);
      return { ...parsed, settings: legacy };
    }
    return parsed;
  } catch {
    const bestSettings = await readBestSettings(settingsFilePath, legacySettingsFilePath);
    const initial = bestSettings ? { ...createDefaultData(), settings: bestSettings } : createDefaultData();
    await writeAppData(dataFilePath, initial);
    return initial;
  }
}

export async function writeAppData(dataFilePath: string, data: AppData) {
  writeChain = writeChain
    .catch(() => undefined)
    .then(async () => {
      const settingsFilePath = getSettingsFilePath(path.dirname(dataFilePath));
      await writeSettings(settingsFilePath, data.settings);
      await writeJsonAtomically(dataFilePath, data);
    });
  await writeChain;
}

