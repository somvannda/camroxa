import { app, BrowserWindow, Menu, dialog, ipcMain, shell, protocol } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createDefaultData, readAppData, writeAppData, getDataFilePath } from "./storage";
import { format } from "node:util";
import type {
  AppData,
  HistoryItem,
  JobEvent,
  JobPayload,
  VideoExportSettings,
  VideoMergeEvent,
  VideoRenderEvent,
  VideoRenderStartInput,
  VideoTemplateListItem,
} from "../shared/app-types";
import type { ContentBulkUpsertTextStylesRequest, ContentDeleteRequest, ContentUpsertRequest } from "../shared/app-types";
import type { ContentBulkUpsertCarModelsRequest } from "../shared/app-types";
import { JobQueue } from "./jobQueue";
import { testPostgresConnection } from "./db/testPostgres";
import { ensureDatabaseAndMigrate } from "./db/migratePostgres";
import { getLatestSunoBatchWithOutputDirs, getLatestSunoOutputDirsBySongUid, getLatestSunoOutputDirsByBatchId } from "./db/sunoTaskStore";
import { downloadFfmpeg } from "./ffmpeg/downloadFfmpeg";
import { pathExists } from "./fs/pathUtils";
import { polishLyricsWithOpenAI } from "./ai/openaiSong";
import { clearPool, generateAndInsert, importAlbums, importOpenings, importTitles, listPool, poolStats } from "./db/phrasePools";
import { clearGenerated } from "./db/songStore";
import { promises as fs } from "node:fs";
import { getDbConfigPath, readDbConfig, writeDbConfig } from "./dbConfig";
import { getAppJson, setAppJson } from "./db/appJsonStore";
import { listProfiles, syncProfiles } from "./db/profileStore";
import { deleteVideoTemplate, getVideoTemplate, listVideoTemplates, upsertVideoTemplate } from "./db/videoTemplateStore";
import {
  scoreImageLumaStddev,
} from "./ai/openaiImage";
import { generateBackgroundWithSlai, generateThumbnailWithSlai } from "./ai/slaiImage";
import {
  bootstrapContent,
  bulkUpsertCarModels,
  deleteCarModel,
  deletePromptTemplate,
  deleteSongDescription,
  deleteSongStructure,
  deleteTextStyle,
  seedBossPresets,
  upsertCarModel,
  upsertPromptTemplate,
  upsertSongDescription,
  upsertSongStructure,
  upsertTextStyle,
  bulkUpsertTextStyles,
} from "./db/contentStore";
import { listImagesInFolder } from "./imageSamples";
import { pollAndDownloadPendingSuno } from "./suno/sunoPoller";
import { startSunoCallbackServer } from "./suno/callbackServer";
import { createNgrokManager } from "./ngrok/ngrokManager";
import { mergeVideosInDirectory } from "./ffmpegVideoMerge";
import { runVideoRender } from "./videoRender";
import { runWebglVideoRender } from "./webglVideoRender";
import { ensureVisualizerEnv } from "./visualizerEnv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ngrok = createNgrokManager();
let callbackServer: Awaited<ReturnType<typeof startSunoCallbackServer>> | null = null;

try {
  app.setName("MusicGenerator");
  app.setAppUserModelId("MusicGenerator");
} catch {
  // ignore
}

protocol.registerSchemesAsPrivileged([
  {
    scheme: "mgsamples",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);

try {
  app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
} catch {
}

function createWindow() {
  const preloadPath = path.join(__dirname, "preload.cjs");
  if (!existsSync(preloadPath)) {
    throw new Error(`Preload not found at ${preloadPath}`);
  }

  const contentWidth = 1670;
  const contentHeight = 1080;

  const win = new BrowserWindow({
    width: contentWidth,
    height: contentHeight,
    useContentSize: true,
    resizable: false,
    minimizable: true,
    maximizable: false,
    fullscreenable: false,
    backgroundColor: "#050a18",
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });


  win.setResizable(false);
  win.setContentSize(contentWidth, contentHeight, true);
  win.setMinimumSize(contentWidth, contentHeight);
  win.setMaximumSize(contentWidth, contentHeight);
  win.setFullScreenable(false);
  win.setMaximizable(false);

  win.on("will-resize", (event) => {
    event.preventDefault();
  });

  win.on("maximize", () => {
    try {
      win.unmaximize();
    } catch {
      return;
    }
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;

  if (devServerUrl) {
    win.loadURL(devServerUrl);
  } else {
    const indexHtmlPath = path.join(app.getAppPath(), "dist", "index.html");
    win.loadFile(indexHtmlPath);
  }

  win.webContents.on("did-fail-load", (_evt, code, desc, validatedURL) => {
    console.log("[renderer] did-fail-load", { code, desc, url: validatedURL });
  });

  win.webContents.on("render-process-gone", (_evt, details) => {
    console.log("[renderer] render-process-gone", details);
  });

  win.on("unresponsive", () => {
    console.log("[window] unresponsive");
  });

  win.webContents.on("did-finish-load", async () => {
    if (devServerUrl) {
      const openDevtools = String(process.env.MG_OPEN_DEVTOOLS || "").trim() === "1";
      if (openDevtools) {
        try {
          win.webContents.openDevTools({ mode: "detach" });
        } catch {
        }
      }
    }
    try {
      const v = await win.webContents.executeJavaScript("window.mgApi?.bridgeVersion ?? null", true);
      console.log("[renderer] mgApi.bridgeVersion", v);
    } catch (e) {
      console.log("[renderer] mgApi check failed", e);
    }
  });

  return win;
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  const win = createWindow();

  protocol.registerFileProtocol("mgsamples", (request, callback) => {
    try {
      const u = new URL(request.url);
      const filePath = u.searchParams.get("path") ?? "";
      if (!filePath) return callback({ error: -6 });
      return callback({ path: filePath });
    } catch {
      return callback({ error: -324 });
    }
  });

  const userDataDir = app.getPath("userData");
  const debugLogPath = path.join(userDataDir, "mg-debug.log");
  const sanitizeLogLine = (s: string) => {
    return String(s || "")
      .replace(/Bearer\s+[A-Za-z0-9._-]+/g, "Bearer <redacted>")
      .replace(/("password"\s*:\s*)"[^"]*"/gi, '$1"<redacted>"')
      .replace(/(DEEPSEEK_API_KEY=)[^\s]+/gi, "$1<redacted>")
      .replace(/(OPENAI_API_KEY=)[^\s]+/gi, "$1<redacted>")
      .replace(/(SLAI(_IMG|_SONG)?_API_KEY=)[^\s]+/gi, "$1<redacted>");
  };
  const writeLogLine = (line: string) => {
    const stamped = `[${new Date().toISOString()}] ${sanitizeLogLine(line)}\n`;
    void fs.appendFile(debugLogPath, stamped).catch(() => undefined);
  };
  const consoleLog = console.log.bind(console);
  const consoleWarn = console.warn.bind(console);
  const consoleError = console.error.bind(console);
  console.log = (...args: unknown[]) => {
    consoleLog(...args);
    writeLogLine(format(...args));
  };
  console.warn = (...args: unknown[]) => {
    consoleWarn(...args);
    writeLogLine(`WARN ${format(...args)}`);
  };
  console.error = (...args: unknown[]) => {
    consoleError(...args);
    writeLogLine(`ERROR ${format(...args)}`);
  };
  console.log("[debug] log file", debugLogPath);
  const dbConfigPath = getDbConfigPath({ isPackaged: app.isPackaged, appPath: app.getAppPath(), execPath: process.execPath });
  const APP_DATA_KEY = "app_data_v1";
  const queue = new JobQueue();
  const migratedDbKeys = new Set<string>();
  const sunoRunDirsByBatchId = new Map<string, { ok: string; alt: string; createdAtMs: number }>();

  const injectDbSettings = (settings: AppData["settings"], cfg: { host: string; port: number; user: string; password: string; database: string }) => {
    return { ...settings, dbHost: cfg.host, dbPort: cfg.port, dbUser: cfg.user, dbPassword: cfg.password, dbName: cfg.database };
  };

  const stripDbConnectionSettings = (settings: AppData["settings"]) => {
    return { ...settings, dbHost: "", dbPort: 5432, dbUser: "", dbPassword: "", dbName: "" };
  };

  async function readDbCfgOrNull() {
    return await readDbConfig(dbConfigPath);
  }

  async function requireDbCfg() {
    const cfg = await readDbCfgOrNull();
    if (!cfg) throw new Error(`Database is not configured. Create ${path.basename(dbConfigPath)} in the app folder or set it in Settings → Database.`);
    return cfg;
  }

  async function readAppDataFromDb(cfg: { host: string; port: number; user: string; password: string; database: string }): Promise<AppData> {
    const base = createDefaultData();
    const stored = await getAppJson<Partial<AppData>>(cfg, APP_DATA_KEY);
    const profiles = await listProfiles(cfg);
    const merged: AppData = {
      ...base,
      ...stored,
      descriptions: [],
      structures: [],
      carModels: [],
      promptTemplates: [],
      textStyles: [],
      profiles,
      settings: {
        ...base.settings,
        ...(stored?.settings ?? {}),
      },
    };
    if (!merged.songDrafts?.length) merged.songDrafts = base.songDrafts;
    merged.settings = injectDbSettings(merged.settings, cfg);
    return merged;
  }

  async function writeAppDataToDb(
    cfg: { host: string; port: number; user: string; password: string; database: string },
    data: AppData,
  ) {
    await syncProfiles(
      cfg,
      (data.profiles ?? []).map((p) => ({
        id: p.id,
        name: p.name,
        folderName: p.folderName,
        runPrefix: p.runPrefix,
        logoPath: p.logoPath,
      })),
    );
    const toStore: AppData = {
      ...data,
      profiles: [],
      descriptions: [],
      structures: [],
      carModels: [],
      promptTemplates: [],
      textStyles: [],
      settings: stripDbConnectionSettings(data.settings),
    };
    await setAppJson(cfg, APP_DATA_KEY, toStore);
  }

  let sunoPollTimer: NodeJS.Timeout | null = null;
  function startSunoPoller() {
    if (sunoPollTimer) return;

    const tick = async () => {
      try {
        const db = await readDbCfgOrNull();
        if (!db) return;
        await ensureMigrated(db);
        const data = await readAppDataFromDb(db);
        const apiKey = String(data.settings.sunoApiKey || "").trim();
        await pollAndDownloadPendingSuno({ db, apiKey, outputDir: data.settings.sunoOutputDir, maxTasksPerRun: 10 });
      } catch {
        return;
      }
    };

    tick().catch(() => undefined);
    sunoPollTimer = setInterval(() => {
      tick().catch(() => undefined);
    }, 30_000);
  }

  function cleanupSunoRunDirs() {
    const cutoff = Date.now() - 6 * 60 * 60 * 1000;
    for (const [k, v] of sunoRunDirsByBatchId) {
      if (v.createdAtMs < cutoff) sunoRunDirsByBatchId.delete(k);
    }
  }

  async function ensureMigrated(cfg: { host: string; port: number; user: string; password: string; database: string }) {
    const key = `${cfg.user}@${cfg.host}:${cfg.port}/${cfg.database}`;
    if (migratedDbKeys.has(key)) return;
    const res = await ensureDatabaseAndMigrate(cfg);
    if (res.ok) migratedDbKeys.add(key);
    else throw new Error(res.message);

    try {
      await seedBossPresets(cfg);
    } catch {
      // ignore seed errors
    }
  }

  function sanitizeFolderSegment(input: string) {
    return String(input || "")
      .toLowerCase()
      .replace(/[^a-z0-9 _.-]+/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\s/g, "-")
      .slice(0, 48);
  }

  async function planNextRunDir(baseDir: string, profileFolderName: string, prefix: string) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const profileFolder = sanitizeFolderSegment(profileFolderName) || "profile";
    const profileDir = path.join(base, profileFolder);
    await fs.mkdir(profileDir, { recursive: true });

    let entries: Array<string> = [];
    try {
      const listed = await fs.readdir(profileDir, { withFileTypes: true });
      entries = listed.filter((d) => d.isDirectory()).map((d) => d.name);
    } catch {
      entries = [];
    }

    const re = /^(?:.*_)?(\d{2,})$/;
    let maxN = 0;
    for (const name of entries) {
      const m = name.match(re);
      if (!m) continue;
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > maxN) maxN = n;
    }

    const cleanPrefix = sanitizeFolderSegment(prefix).replace(/-/g, "_");
    for (let n = maxN + 1; n < maxN + 10_000; n += 1) {
      const suffix = String(n).padStart(2, "0");
      const runFolderName = cleanPrefix ? `${cleanPrefix}_${suffix}` : suffix;
      const runDir = path.join(profileDir, runFolderName);
      try {
        await fs.mkdir(runDir, { recursive: false });
        return runDir;
      } catch {
        continue;
      }
    }

    throw new Error("Failed to allocate a new run folder");
  }

  function sanitizeRunLabel(input: string) {
    return String(input || "")
      .replace(/[^a-zA-Z0-9 _.-]+/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\s/g, "-")
      .slice(0, 64);
  }

  function escapeRegex(input: string) {
    return String(input || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  async function planNextRunDirByLabel(baseDir: string, profileFolderName: string, label: string) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const profileFolder = sanitizeFolderSegment(profileFolderName) || "profile";
    const profileDir = path.join(base, profileFolder);
    await fs.mkdir(profileDir, { recursive: true });

    const baseName = sanitizeRunLabel(label) || "run";
    let entries: Array<string> = [];
    try {
      const listed = await fs.readdir(profileDir, { withFileTypes: true });
      entries = listed.filter((d) => d.isDirectory()).map((d) => d.name);
    } catch {
      entries = [];
    }

    const exactExists = entries.includes(baseName);
    if (!exactExists) {
      const runDir = path.join(profileDir, baseName);
      await fs.mkdir(runDir, { recursive: false });
      return runDir;
    }

    const re = new RegExp(`^${escapeRegex(baseName)}_(\\d{2,})$`);
    let maxN = 1;
    for (const name of entries) {
      const m = name.match(re);
      if (!m) continue;
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > maxN) maxN = n;
    }

    for (let n = maxN + 1; n < maxN + 10_000; n += 1) {
      const suffix = String(n).padStart(2, "0");
      const runFolderName = `${baseName}_${suffix}`;
      const runDir = path.join(profileDir, runFolderName);
      try {
        await fs.mkdir(runDir, { recursive: false });
        return runDir;
      } catch {
        continue;
      }
    }
    throw new Error("Failed to allocate a new run folder");
  }

  async function planNextPairedRunDirsByLabel(
    baseDir: string,
    okProfileFolderName: string,
    altProfileFolderName: string | null,
    label: string,
  ) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const okFolder = sanitizeFolderSegment(okProfileFolderName) || "profile";
    const altFolder = altProfileFolderName ? sanitizeFolderSegment(altProfileFolderName) || "profile" : okFolder;
    const okProfileDir = path.join(base, okFolder);
    const altProfileDir = path.join(base, altFolder);
    await fs.mkdir(okProfileDir, { recursive: true });
    await fs.mkdir(altProfileDir, { recursive: true });

    const baseName = sanitizeRunLabel(label) || "run";

    const readDirs = async (dir: string) => {
      try {
        const listed = await fs.readdir(dir, { withFileTypes: true });
        return listed.filter((d) => d.isDirectory()).map((d) => d.name);
      } catch {
        return [] as string[];
      }
    };

    const [okEntries, altEntries] = await Promise.all([readDirs(okProfileDir), readDirs(altProfileDir)]);
    const re = new RegExp(`^${escapeRegex(baseName)}_(\\d{2,})$`);
    const getMaxIndex = (entries: string[]) => {
      let maxN = entries.includes(baseName) ? 1 : 0;
      for (const name of entries) {
        const m = name.match(re);
        if (!m) continue;
        const n = Number(m[1]);
        if (Number.isFinite(n) && n > maxN) maxN = n;
      }
      return maxN;
    };

    const maxOk = getMaxIndex(okEntries);
    const maxAlt = getMaxIndex(altEntries);
    const maxBoth = Math.max(maxOk, maxAlt);
    const runFolderName = maxBoth === 0 ? baseName : `${baseName}_${String(maxBoth + 1).padStart(2, "0")}`;

    const okRunDir = path.join(okProfileDir, runFolderName);
    const altRunDir = path.join(altProfileDir, runFolderName);
    await fs.mkdir(okRunDir, { recursive: false });
    if (altRunDir !== okRunDir) await fs.mkdir(altRunDir, { recursive: false });
    return { okRunDir, altRunDir };
  }

  startSunoPoller();

  (async () => {
    callbackServer = await startSunoCallbackServer({
      path: "/suno/callback",
      onCallback: async (payload) => {
        try {
          const db = await readDbCfgOrNull();
          if (!db) return;
          await ensureMigrated(db);
          const data = await readAppDataFromDb(db);
          const apiKey = String(data.settings.sunoApiKey || "").trim();
          await pollAndDownloadPendingSuno({ db, apiKey, outputDir: data.settings.sunoOutputDir, maxTasksPerRun: 25 });
          console.log("[sunoCallback] received", typeof payload);
        } catch {
          return;
        }
      },
    });
  })().catch(() => undefined);

  ipcMain.on("mg:preload:ready", (_evt, payload: { bridgeVersion: number }) => {
    console.log("[preload] ready", payload);
  });

  queue.onEvent((event: JobEvent) => {
    win.webContents.send("mg:jobEvent", event);
  });

  ipcMain.handle("mg:getData", async () => {
    const userDataDir = app.getPath("userData");
    const dataFilePath = getDataFilePath(userDataDir);
    let localData: AppData | null = null;
    try {
      localData = await readAppData(dataFilePath);
    } catch {
      // ignore
    }

    const db = await readDbCfgOrNull();
    if (!db) {
      if (localData) return localData;
      const base = createDefaultData();
      return {
        ...base,
        descriptions: [],
        structures: [],
        carModels: [],
        promptTemplates: [],
        textStyles: [],
        settings: { ...base.settings, dbHost: "", dbPort: 5432, dbUser: "", dbPassword: "", dbName: "" },
      };
    }
    await ensureMigrated(db);
    const dbData = await readAppDataFromDb(db);
    if (localData && localData.settings) {
      const mergedSettings = { ...dbData.settings };
      for (const [k, v] of Object.entries(localData.settings)) {
        const existing = mergedSettings[k as keyof typeof mergedSettings];
        if (typeof existing === "undefined" || existing === null) {
          // @ts-expect-error dynamic assign
          mergedSettings[k as keyof typeof mergedSettings] = v;
        }
      }
      dbData.settings = mergedSettings;
    }
    return dbData;
  });

  ipcMain.handle("mg:setData", async (_evt, data: AppData) => {
    try {
      const userDataDir = app.getPath("userData");
      const dataFilePath = getDataFilePath(userDataDir);
      await writeAppData(dataFilePath, data);
    } catch {
      // ignore
    }

    const s = data.settings;
    const candidate = {
      host: s.dbHost,
      port: s.dbPort,
      user: s.dbUser,
      password: s.dbPassword,
      database: s.dbName,
    };
    if (String(candidate.host || "").trim() && String(candidate.user || "").trim() && String(candidate.database || "").trim()) {
      await writeDbConfig(dbConfigPath, candidate);
    }
    const db = await readDbCfgOrNull();
    if (!db) return { ok: false as const, message: `Database is not configured. Create ${path.basename(dbConfigPath)} in the app folder.` };
    await ensureMigrated(db);
    await writeAppDataToDb(db, data);
    return { ok: true as const };
  });

  ipcMain.handle("mg:appendHistory", async (_evt, item: HistoryItem) => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const data = await readAppDataFromDb(db);
      const next: AppData = {
        ...data,
        history: [item, ...(data.history ?? [])].slice(0, 2000),
      };
      await writeAppDataToDb(db, next);
      return { ok: true as const };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Failed to append history" };
    }
  });

  ipcMain.handle("mg:reset", async () => {
    const db = await requireDbCfg();
    await ensureMigrated(db);
    const base = createDefaultData();
    const next: AppData = {
      ...base,
      descriptions: [],
      structures: [],
      carModels: [],
      promptTemplates: [],
      textStyles: [],
      profiles: [],
      history: [],
      songs: [],
    };
    await writeAppDataToDb(db, next);
    return await readAppDataFromDb(db);
  });

  ipcMain.handle("mg:close", async () => {
    win.close();
    return { ok: true };
  });

  ipcMain.handle("mg:queue:enqueue", async (_evt, payload: JobPayload) => {
    console.log("[queue:enqueue]", {
      jobType: payload.jobType,
      action: payload.jobType === "workflow" ? payload.action : undefined,
      batchId: (payload as { batchId?: string }).batchId,
    });
    if ((payload.jobType === "workflow" && payload.action === "generate") || payload.jobType === "suno") {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const data = await readAppDataFromDb(db);
      const s = data.settings;
      payload.db = db;

      if (payload.jobType === "suno") {
        payload.downloadsDir = s.downloadsDir;
        payload.mergedDir = s.mergedDir;
        payload.ffmpegPath = s.ffmpegPath;
        payload.mergeEnabled = s.sunoMergeEnabled;
        payload.mergeGroupSize = s.sunoMergeGroupSize;
        payload.version = payload.version ?? s.sunoDefaultVersion;
        payload.sunoTimeoutMs = s.sunoTimeoutMs;
        payload.sunoRetryCount = s.sunoRetryCount;
        payload.sunoApiKey = s.sunoApiKey;
        const okId = payload.profileOkId || s.activeProfileOkId || s.activeProfileId;
        const altId = payload.profileAltId || s.activeProfileAltId;
        const okProfile = okId ? data.profiles.find((p) => p.id === okId) : null;
        const altProfile = altId ? data.profiles.find((p) => p.id === altId) : null;
        if (!okProfile) {
          throw new Error("No OK profile selected. Select a profile in Settings → Profiles.");
        }
        const batchKey = String((payload as { batchId?: string }).batchId ?? "").trim();
        let outOk = "";
        let outAlt = "";

        if (batchKey) {
          const res = await getLatestSunoOutputDirsByBatchId(db, batchKey);
          if (res.ok && res.okDir) {
            outOk = res.okDir;
            outAlt = res.altDir || outOk;
          }
        }

        if (!outOk) {
          const runLabel = String(payload.sunoRunLabel || "").trim();
          const out = runLabel
            ? await planNextPairedRunDirsByLabel(s.sunoOutputDir, okProfile.folderName, altProfile?.folderName ?? null, runLabel)
            : {
                okRunDir: await planNextRunDir(s.sunoOutputDir, okProfile.folderName, okProfile.runPrefix),
                altRunDir: altProfile ? await planNextRunDir(s.sunoOutputDir, altProfile.folderName, altProfile.runPrefix) : "",
              };
          outOk = out.okRunDir;
          outAlt = altProfile ? out.altRunDir : outOk;
        }

        payload.sunoOutputDirOk = outOk;
        payload.sunoOutputDirAlt = outAlt;
        payload.sunoOutputDir = outOk;
        payload.sunoCallbackUrl = s.sunoCallbackUrl;
      }

      if (payload.jobType === "workflow" && payload.action === "generate" && payload.sunoAutoSubmit) {
        payload.sunoApiKey = s.sunoApiKey;
        payload.sunoCallbackUrl = s.sunoCallbackUrl;
        payload.sunoVersion = s.sunoDefaultVersion;
        const okId = payload.profileOkId || s.activeProfileOkId || s.activeProfileId;
        const altId = payload.profileAltId || s.activeProfileAltId;
        const okProfile = okId ? data.profiles.find((p) => p.id === okId) : null;
        const altProfile = altId ? data.profiles.find((p) => p.id === altId) : null;
        if (!okProfile) {
          throw new Error("No OK profile selected. Select a profile in Settings → Profiles.");
        }
        const batchKey = String((payload as { batchId?: string }).batchId ?? "").trim();
        cleanupSunoRunDirs();
        const existing = batchKey ? sunoRunDirsByBatchId.get(batchKey) : null;
        let outOk = "";
        let outAlt = "";

        if (existing) {
          outOk = existing.ok;
          outAlt = existing.alt;
        } else if (batchKey) {
          const res = await getLatestSunoOutputDirsByBatchId(db, batchKey);
          if (res.ok && res.okDir) {
            outOk = res.okDir;
            outAlt = res.altDir || outOk;
            sunoRunDirsByBatchId.set(batchKey, { ok: outOk, alt: outAlt, createdAtMs: Date.now() });
          }
        }

        if (!outOk) {
          const runLabel = String(payload.sunoRunLabel || "").trim();
          const out = runLabel
            ? await planNextPairedRunDirsByLabel(s.sunoOutputDir, okProfile.folderName, altProfile?.folderName ?? null, runLabel)
            : {
                okRunDir: await planNextRunDir(s.sunoOutputDir, okProfile.folderName, okProfile.runPrefix),
                altRunDir: altProfile ? await planNextRunDir(s.sunoOutputDir, altProfile.folderName, altProfile.runPrefix) : "",
              };
          outOk = out.okRunDir;
          outAlt = altProfile ? out.altRunDir : outOk;
          if (batchKey) sunoRunDirsByBatchId.set(batchKey, { ok: outOk, alt: outAlt, createdAtMs: Date.now() });
        }

        payload.sunoOutputDirOk = outOk;
        payload.sunoOutputDirAlt = outAlt;
      }
    }
    return queue.enqueue(payload);
  });

  ipcMain.handle("mg:queue:cancel", async (_evt, jobId: string) => {
    return queue.cancel(jobId);
  });

  ipcMain.handle("mg:ngrok:status", async () => {
    const s = ngrok.status();
    return { ...s, callbackPort: callbackServer?.port ?? null };
  });

  ipcMain.handle("mg:ngrok:start", async (_evt, input: { ngrokPath?: string } | undefined) => {
    const port = callbackServer?.port;
    if (!port) return { ok: false as const, message: "Callback server is not ready" };
    const s = await ngrok.start({ ngrokPath: input?.ngrokPath, localPort: port, callbackPath: "/suno/callback" });
    return { ok: true as const, status: s };
  });

  ipcMain.handle("mg:ngrok:stop", async () => {
    const s = await ngrok.stop();
    return { ok: true as const, status: s };
  });

  ipcMain.handle("mg:queue:state", async () => {
    return queue.getState();
  });

  ipcMain.handle("mg:openPath", async (_evt, targetPath: string) => {
    return await shell.openPath(targetPath);
  });

  ipcMain.handle("mg:pathExists", async (_evt, targetPath: string) => {
    return { exists: await pathExists(targetPath) };
  });

  ipcMain.handle("mg:showItemInFolder", async (_evt, targetPath: string) => {
    shell.showItemInFolder(targetPath);
    return { ok: true };
  });

  ipcMain.handle("mg:suno:getSongOutputDirs", async (_evt, songUid: string) => {
    const db = await requireDbCfg();
    await ensureMigrated(db);
    const dirs = await getLatestSunoOutputDirsBySongUid(db, songUid);
    return { ok: true as const, ...dirs };
  });

  ipcMain.handle("mg:suno:getBatchRunDirs", async (_evt, batchId: string) => {
    const key = String(batchId || "").trim();
    if (!key) return { ok: false as const, message: "Batch ID is empty" };
    cleanupSunoRunDirs();
    const existing = sunoRunDirsByBatchId.get(key) ?? null;
    return { ok: true as const, okDir: existing?.ok ?? null, altDir: existing?.alt ?? null };
  });

  ipcMain.handle(
    "mg:pickPath",
    async (
      _evt,
      opts: { kind: "file" | "directory"; defaultPath?: string; title?: string; filters?: { name: string; extensions: string[] }[] },
    ) => {
      const props = opts.kind === "directory" ? (["openDirectory"] as const) : (["openFile"] as const);
      const result = await dialog.showOpenDialog(win, {
        title: opts.title,
        defaultPath: opts.defaultPath,
        properties: [...props],
        filters: opts.filters,
      });
      if (result.canceled) return { canceled: true as const };
      return { canceled: false as const, path: result.filePaths[0] ?? "" };
    },
  );

  ipcMain.handle("mg:pickDirectories", async (_evt, opts?: { title?: string; defaultPath?: string }) => {
    const result = await dialog.showOpenDialog(win, {
      title: opts?.title,
      defaultPath: opts?.defaultPath,
      properties: ["openDirectory", "multiSelections"],
    });
    if (result.canceled) return { canceled: true as const };
    const paths = (result.filePaths ?? []).filter((p) => typeof p === "string" && p.trim().length > 0);
    return { canceled: false as const, paths };
  });

  let videoMergeRunning = false;

  ipcMain.handle(
    "mg:videoMerge:start",
    async (_evt, input: { directories: string[]; exportSettings: VideoExportSettings }) => {
      if (videoMergeRunning) return { ok: false as const, message: "Video merge is already running" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const data = await readAppDataFromDb(db);
      const s = data.settings;
      const ffmpegPath = String(s.ffmpegPath || "").trim();
      if (!ffmpegPath) return { ok: false as const, message: "FFmpeg path is not configured" };
      if (!(await pathExists(ffmpegPath))) return { ok: false as const, message: "FFmpeg path does not exist" };

      const directories = Array.isArray(input.directories)
        ? input.directories.filter((d) => typeof d === "string" && d.trim().length > 0)
        : [];
      if (!directories.length) return { ok: false as const, message: "No directories selected" };

      const exportSettings = input.exportSettings;
      const runId = randomUUID();
      videoMergeRunning = true;

      const total = directories.length;
      const send = (evt: VideoMergeEvent) => {
        try {
          win.webContents.send("mg:videoMergeEvent", evt);
        } catch {
          return;
        }
      };

      for (let i = 0; i < directories.length; i += 1) {
        send({ runId, index: i + 1, total, directory: directories[i]!, status: "pending", message: "Pending" });
      }

      setTimeout(async () => {
        try {
          for (let i = 0; i < directories.length; i += 1) {
            const dir = directories[i]!;
            send({ runId, index: i + 1, total, directory: dir, status: "running", message: "Scanning..." });
            try {
              const r = await mergeVideosInDirectory({ ffmpegPath, directory: dir, exportSettings });
              if (r.ok) {
                send({
                  runId,
                  index: i + 1,
                  total,
                  directory: dir,
                  status: "done",
                  message: `Merged ${r.videoCount} videos`,
                  outputPath: r.outputPath ?? undefined,
                });
              } else {
                send({ runId, index: i + 1, total, directory: dir, status: "failed", message: r.message });
              }
            } catch (e) {
              const msg = e instanceof Error ? e.message : "FFmpeg failed";
              send({ runId, index: i + 1, total, directory: dir, status: "failed", message: msg });
            }
          }
        } finally {
          videoMergeRunning = false;
        }
      }, 0);

      return { ok: true as const, runId };
    },
  );

  let videoRenderRunning = false;
  type PreviewWorkerPending = {
    resolve: (v: { ok: true } | { ok: false; message: string }) => void;
    reject: (e: unknown) => void;
    timer: NodeJS.Timeout;
  };
  let previewWorker:
    | {
        child: ChildProcessWithoutNullStreams;
        buf: string;
        pending: Map<string, PreviewWorkerPending>;
      }
    | null = null;
  let visualizerEnvCache: { pythonPath: string; atMs: number } | null = null;

  const stopPreviewWorker = async () => {
    const w = previewWorker;
    previewWorker = null;
    visualizerEnvCache = visualizerEnvCache;
    if (!w) return;
    for (const p of w.pending.values()) {
      try {
        clearTimeout(p.timer);
      } catch {
      }
      p.resolve({ ok: false, message: "Preview worker stopped" });
    }
    w.pending.clear();
    try {
      w.child.kill();
    } catch {
    }
  };

  const ensureVisualizerEnvCached = async (pythonPathUsed: string, projectRoot: string) => {
    const now = Date.now();
    if (visualizerEnvCache && now - visualizerEnvCache.atMs < 10 * 60 * 1000 && visualizerEnvCache.pythonPath) {
      return { ok: true as const, pythonPath: visualizerEnvCache.pythonPath };
    }
    const env = await ensureVisualizerEnv({
      basePythonPath: pythonPathUsed,
      appPath: projectRoot,
      userDataPath: app.getPath("userData"),
      onStatus: () => undefined,
    });
    if (env.ok === false) return env;
    visualizerEnvCache = { pythonPath: env.pythonPath, atMs: now };
    return { ok: true as const, pythonPath: env.pythonPath };
  };

  const ensurePreviewWorker = async (pythonPathUsed: string, projectRoot: string) => {
    if (previewWorker) return { ok: true as const };
    const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
    if (env.ok === false) return env;
    const scriptPath = path.join(projectRoot, "visualizer", "preview_worker.py");
    if (!existsSync(scriptPath)) return { ok: false as const, message: "preview_worker.py not found" };
    const child = spawn(env.pythonPath, ["-u", "-m", "visualizer.preview_worker"], {
      windowsHide: true,
      cwd: projectRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    const w = { child, buf: "", pending: new Map<string, PreviewWorkerPending>() };
    previewWorker = w;
    child.stderr?.on("data", (chunk) => {
      const s = String(chunk || "").trim();
      if (s) console.error(`[previewWorker stderr]: ${s}`);
    });
    child.stdout.on("data", (chunk) => {
      const s = String(chunk || "");
      w.buf += s;
      for (;;) {
        const idx = w.buf.indexOf("\n");
        if (idx < 0) break;
        const line = w.buf.slice(0, idx).trim();
        w.buf = w.buf.slice(idx + 1);
        if (!line) continue;
        let msg: any = null;
        try {
          msg = JSON.parse(line);
        } catch {
          continue;
        }
        const id = String(msg?.id || "").trim();
        if (!id) continue;
        const pending = w.pending.get(id);
        if (!pending) continue;
        w.pending.delete(id);
        try {
          clearTimeout(pending.timer);
        } catch {
        }
        if (msg.ok === true) pending.resolve({ ok: true });
        else pending.resolve({ ok: false, message: String(msg?.message || "Preview worker failed") });
      }
    });
    const onExit = () => {
      if (previewWorker?.child === child) previewWorker = null;
      for (const p of w.pending.values()) {
        try {
          clearTimeout(p.timer);
        } catch {
        }
        p.resolve({ ok: false, message: "Preview worker exited" });
      }
      w.pending.clear();
    };
    child.on("exit", onExit);
    child.on("error", onExit);
    return { ok: true as const };
  };

  const renderPreviewWithWorker = async (input: {
    pythonPathUsed: string;
    projectRoot: string;
    mp3Path: string;
    backgroundPath: string;
    templateJsonB64: string;
    logoPath: string;
    fps: number;
    width: number;
    height: number;
    frame: number;
    outPngPath: string;
  }) => {
    const ready = await ensurePreviewWorker(input.pythonPathUsed, input.projectRoot);
    if (ready.ok === false) return ready;
    const w = previewWorker;
    if (!w) return { ok: false as const, message: "Preview worker is not running" };
    const id = randomUUID();
    const timeoutMs = 20000;
    const r = await new Promise<{ ok: true } | { ok: false; message: string }>((resolve, reject) => {
      const timer = setTimeout(() => {
        w.pending.delete(id);
        resolve({ ok: false, message: "Preview timeout" });
      }, timeoutMs);
      w.pending.set(id, { resolve, reject, timer });
      try {
        const payload = {
          id,
          cmd: "render",
          mp3Path: input.mp3Path,
          backgroundPath: input.backgroundPath,
          templateJsonB64: input.templateJsonB64 || "",
          logoPath: input.logoPath || "",
          fps: input.fps,
          width: input.width,
          height: input.height,
          frame: input.frame,
          outPngPath: input.outPngPath,
        };
        w.child.stdin.write(`${JSON.stringify(payload)}\n`);
      } catch (e) {
        try {
          clearTimeout(timer);
        } catch {
        }
        w.pending.delete(id);
        reject(e);
      }
    });
    return r;
  };

  let livePreviewWorker: { child: ReturnType<typeof spawn>; buf: string } | null = null;

  const stopLivePreviewWorker = () => {
    if (!livePreviewWorker) return;
    try {
      livePreviewWorker.child.kill();
    } catch {}
    livePreviewWorker = null;
  };

  ipcMain.handle("mg:videoRender:startLivePreview", async (_evt, input: any) => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      let data = await readAppDataFromDb(db);
      let s = data.settings;
      
      const probeCmd = async (cmd: string, args: string[]) => {
        return await new Promise<{ ok: true; stdout: string } | { ok: false }>((resolve) => {
          const child = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
          let stdout = "";
          const timer = setTimeout(() => { try { child.kill(); } catch {} resolve({ ok: false }); }, 3000);
          child.stdout.on("data", (c) => { stdout += String(c || ""); });
          child.on("error", () => { clearTimeout(timer); resolve({ ok: false }); });
          child.on("close", (code) => { clearTimeout(timer); if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") }); resolve({ ok: false }); });
        });
      };
      
      const detectPython = async (candidate: string) => {
        const cmd = String(candidate || "").trim();
        if (!cmd) return null;
        const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
        if (r.ok === false) return null;
        const resolved = String(r.stdout || "").trim();
        if (resolved && existsSync(resolved)) return resolved;
        return cmd;
      };
      
      const pythonPathStored = String(s.pythonPath || "").trim();
      const pythonPathUsed = (await detectPython(pythonPathStored)) ?? (await detectPython("py")) ?? (await detectPython("python")) ?? (await detectPython("python3")) ?? "";
      if (!pythonPathUsed) return { ok: false, message: "Python executable not found." };
      
      const appPath = app.getAppPath();
      const projectRoot = existsSync(path.join(appPath, "package.json")) ? appPath : process.cwd();
      const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
      if (env.ok === false) return env;

      stopLivePreviewWorker();

      const mp3PathRaw = String(input?.mp3Path || "").trim();
      const mp3Path = mp3PathRaw && (await pathExists(mp3PathRaw)) ? mp3PathRaw : "synthetic";
      const backgroundPathRaw = String(input?.backgroundPath || "").trim();
      const backgroundPath = backgroundPathRaw && (await pathExists(backgroundPathRaw)) ? backgroundPathRaw : "";
      const logoPath = String(input?.logoPath || "").trim();

      const templateJsonB64 = Buffer.from(JSON.stringify(input.template ?? {}), "utf-8").toString("base64");
      
      const w = 1280;
      const h = 720;

      const args = [
        "-u",
        "-m", "visualizer.main",
        mp3Path,
        "dummy.json",
        "--background", backgroundPath,
        "--logo", logoPath,
        "--templateB64", templateJsonB64,
        "--width", String(w),
        "--height", String(h),
        "--fps", "60",
        "--livePreview"
      ];

      const child = spawn(env.pythonPath, args, {
        windowsHide: false,
        cwd: projectRoot,
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
      });

      livePreviewWorker = { child, buf: "" };

      child.stderr?.on("data", (chunk) => {
        const s = String(chunk || "").trim();
        if (s) console.error(`[livePreview stderr]: ${s}`);
      });

      child.stdout.on("data", (chunk) => {
        const s = String(chunk || "");
        if (!livePreviewWorker) return;
        livePreviewWorker.buf += s;
        for (;;) {
          const idx = livePreviewWorker.buf.indexOf("\n");
          if (idx < 0) break;
          const line = livePreviewWorker.buf.slice(0, idx).trim();
          livePreviewWorker.buf = livePreviewWorker.buf.slice(idx + 1);
          if (!line) continue;
          if (!line.startsWith("MG_EVENT ")) console.log(`[livePreview stdout]: ${line}`);
        }
      });

      child.on("exit", () => {
        if (livePreviewWorker?.child === child) livePreviewWorker = null;
      });

      return { ok: true };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Failed to start live preview" };
    }
  });

  ipcMain.handle("mg:videoRender:updateLivePreview", async (_evt, input: any) => {
    if (!livePreviewWorker) return { ok: false, message: "Live preview is not running" };
    try {
      const payload: any = {};
      if (typeof input.time === "number") payload.time = input.time;
      if (input.template) payload.templateB64 = Buffer.from(JSON.stringify(input.template), "utf-8").toString("base64");
      if (typeof input.backgroundPath === "string") payload.backgroundPath = input.backgroundPath;
      if (typeof input.logoPath === "string") payload.logoPath = input.logoPath;
      if (typeof input.audioPath === "string") payload.audioPath = input.audioPath;
      
      livePreviewWorker.child.stdin.write(`${JSON.stringify(payload)}\n`);
      return { ok: true };
    } catch (e) {
      return { ok: false, message: "Failed to send update" };
    }
  });

  ipcMain.handle("mg:videoRender:stopLivePreview", async () => {
    stopLivePreviewWorker();
    return { ok: true };
  });

  ipcMain.handle("mg:videoRender:start", async (_evt, input: VideoRenderStartInput) => {
    if (videoRenderRunning) return { ok: false as const, message: "Video render is already running" };
    const db = await requireDbCfg();
    await ensureMigrated(db);
    let data = await readAppDataFromDb(db);
    let s = data.settings;

    const probeCmd = async (cmd: string, args: string[]) => {
      return await new Promise<{ ok: true; stdout: string } | { ok: false }>((resolve) => {
        const child = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
        let stdout = "";
        const timer = setTimeout(() => {
          try {
            child.kill();
          } catch {
          }
          resolve({ ok: false });
        }, 3000);
        child.stdout.on("data", (c) => {
          stdout += String(c || "");
        });
        child.on("error", () => {
          clearTimeout(timer);
          resolve({ ok: false });
        });
        child.on("close", (code) => {
          clearTimeout(timer);
          if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") });
          resolve({ ok: false });
        });
      });
    };

    const detectFfmpeg = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      if (existsSync(cmd)) return cmd;
      const r = await probeCmd(cmd, ["-version"]);
      if (r.ok === false) return null;
      return cmd;
    };

    const ffmpegPathStored = String(s.ffmpegPath || "").trim();
    const ffmpegPathUsed =
      (await detectFfmpeg(ffmpegPathStored)) ??
      (await detectFfmpeg("ffmpeg")) ??
      (await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe")) ??
      (await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe")) ??
      "";
    if (!ffmpegPathUsed) return { ok: false as const, message: "FFmpeg was not found. Set FFmpeg path in Settings → Paths." };

    if (ffmpegPathStored !== ffmpegPathUsed) {
      try {
        data = { ...data, settings: { ...data.settings, ffmpegPath: ffmpegPathUsed } };
        s = data.settings;
        await writeAppDataToDb(db, data);
      } catch {
      }
    }

    const mp3Path = String(input?.mp3Path || "").trim();
    const backgroundPath = String(input?.backgroundPath || "").trim();
    const outputDir = String(input?.outputDir || "").trim();
    const templateId = String(input?.templatePath || "").trim();
    const logoPath = String(input?.logoPath || "").trim();
    if (!mp3Path) return { ok: false as const, message: "MP3 path is required" };
    if (!backgroundPath) return { ok: false as const, message: "Background image path is required" };
    if (!outputDir) return { ok: false as const, message: "Output directory is required" };

    if (!(await pathExists(mp3Path))) return { ok: false as const, message: "MP3 file does not exist" };
    if (!(await pathExists(backgroundPath))) return { ok: false as const, message: "Background file does not exist" };
    if (logoPath && !(await pathExists(logoPath))) return { ok: false as const, message: "Logo file does not exist" };

    const detectPython = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
      if (r.ok === false) return null;
      const resolved = String(r.stdout || "").trim();
      if (resolved && existsSync(resolved)) return resolved;
      return cmd;
    };

    const pythonPathStored = String(s.pythonPath || "").trim();
    const pythonPathUsed =
      (await detectPython(pythonPathStored)) ?? (await detectPython("py")) ?? (await detectPython("python")) ?? (await detectPython("python3")) ?? "";
    if (!pythonPathUsed) return { ok: false as const, message: "Python executable was not found. Set Python path in Settings → Paths." };

    if (pythonPathStored !== pythonPathUsed) {
      try {
        data = { ...data, settings: { ...data.settings, pythonPath: pythonPathUsed } };
        s = data.settings;
        await writeAppDataToDb(db, data);
      } catch {
      }
    }

    let templateJsonB64 = "";
    if (templateId) {
      const tpl = await getVideoTemplate(db, templateId);
      if (tpl) {
        templateJsonB64 = Buffer.from(JSON.stringify(tpl.template ?? {}), "utf-8").toString("base64");
      } else if (templateId.toLowerCase().endsWith(".json") && (await pathExists(templateId))) {
        const raw = await fs.readFile(templateId, "utf-8");
        const parsed = JSON.parse(raw) as unknown;
        templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
      } else {
        return { ok: false as const, message: "Template not found" };
      }
    }

    try {
      await fs.mkdir(outputDir, { recursive: true });
    } catch {
      return { ok: false as const, message: "Could not create output directory" };
    }

    const runId = randomUUID();
    videoRenderRunning = true;

    const send = (evt: VideoRenderEvent) => {
      try {
        win.webContents.send("mg:videoRenderEvent", evt);
      } catch {
        return;
      }
    };

    send({ runId, status: "pending", message: "Queued", progress: 0 });

    setTimeout(async () => {
      try {
        send({ runId, status: "running", message: "Preparing renderer...", progress: 0 });
        const appPath = app.getAppPath();
        const projectRoot = existsSync(path.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnv({
          basePythonPath: pythonPathUsed,
          appPath: projectRoot,
          userDataPath: app.getPath("userData"),
          onStatus: (message) => send({ runId, status: "running", message, progress: 0 }),
        });
        if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });
        const parseRes = (r: unknown) => {
          const s = String(r || "").trim();
          const m = s.match(/^(\d+)x(\d+)$/);
          const w = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w, h };
        };
        const res = parseRes(s.videoExport?.resolution ?? "1920x1080");
        const r = await runVideoRender({
          pythonPath: env.pythonPath,
          ffmpegPath: ffmpegPathUsed,
          appPath: projectRoot,
          input: {
            mp3Path,
            backgroundPath,
            outputDir,
            templateJsonB64: templateJsonB64 || undefined,
            logoPath: logoPath || undefined,
            fps: s.videoExport?.fps ?? 30,
            width: res.w,
            height: res.h,
            renderer: "gpu",
          },
          runId,
          onEvent: (evt) => send(evt),
        });
        if (r.ok === true) {
          send({ runId, status: "done", message: "Done", progress: 1, outputPath: r.outputPath });
        } else {
          send({ runId, status: "failed", message: r.message, progress: 0 });
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Video render failed";
        send({ runId, status: "failed", message: msg, progress: 0 });
      } finally {
        videoRenderRunning = false;
      }
    }, 0);

    return { ok: true as const, runId };
  });

  let videoRenderCancelFlag = false;

  ipcMain.handle("mg:videoRender:stop", async () => {
    videoRenderCancelFlag = true;
    ipcMain.emit("mg:videoRender:stop");
    return { ok: true };
  });

  ipcMain.handle("mg:listMp3s", async (_evt, dirPath: string) => {
    try {
      const files = await fs.readdir(dirPath, { withFileTypes: true });
      const mp3Files = files
        .filter(f => f.isFile() && f.name.toLowerCase().endsWith(".mp3"))
        .map(f => ({ path: path.join(dirPath, f.name), name: f.name }));
      return { ok: true, files: mp3Files };
    } catch {
      return { ok: false, files: [] };
    }
  });

  ipcMain.handle(
    "mg:videoRender:startBatch",
    async (
      _evt,
      input: { mp3DirPath: string; backgroundPath: string; template: unknown; logoPath?: string; outputDir: string; engine?: "python" | "webgl" },
    ) => {
    if (videoRenderRunning) return { ok: false as const, message: "Video render is already running" };
    videoRenderCancelFlag = false;
    
    const mp3DirPath = String(input.mp3DirPath || "").trim();
    if (!mp3DirPath || !existsSync(mp3DirPath)) return { ok: false as const, message: "Valid MP3 directory is required" };
    
    // Find all mp3s
    let mp3Files: string[] = [];
    try {
      const files = await fs.readdir(mp3DirPath, { withFileTypes: true });
      mp3Files = files.filter(f => f.isFile() && f.name.toLowerCase().endsWith(".mp3")).map(f => path.join(mp3DirPath, f.name));
    } catch {
      return { ok: false as const, message: "Failed to read MP3 directory" };
    }
    
    if (mp3Files.length === 0) return { ok: false as const, message: "No MP3 files found in directory" };
    
    const db = await requireDbCfg();
    await ensureMigrated(db);
    let data = await readAppDataFromDb(db);
    let s = data.settings;

    const probeCmd = async (cmd: string, args: string[]) => {
      return await new Promise<{ ok: true; stdout: string } | { ok: false }>((resolve) => {
        const child = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
        let stdout = "";
        const timer = setTimeout(() => {
          try { child.kill(); } catch {}
          resolve({ ok: false });
        }, 3000);
        child.stdout.on("data", (c) => { stdout += String(c || ""); });
        child.on("error", () => {
          clearTimeout(timer);
          resolve({ ok: false });
        });
        child.on("close", (code) => {
          clearTimeout(timer);
          if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") });
          resolve({ ok: false });
        });
      });
    };

    const detectFfmpeg = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      if (existsSync(cmd)) return cmd;
      const r = await probeCmd(cmd, ["-version"]);
      if (r.ok === false) return null;
      return cmd;
    };

    const ffmpegPathStored = String(s.ffmpegPath || "").trim();
    const ffmpegPathUsed = (await detectFfmpeg(ffmpegPathStored)) ?? (await detectFfmpeg("ffmpeg")) ?? "";
    if (!ffmpegPathUsed) return { ok: false as const, message: "FFmpeg was not found. Set FFmpeg path in Settings → Paths." };

    const backgroundPath = String(input.backgroundPath || "").trim();
    const outputDir = String(input.outputDir || "").trim();
    const logoPath = String(input.logoPath || "").trim();
    
    if (!backgroundPath) return { ok: false as const, message: "Background image path is required" };
    if (!outputDir) return { ok: false as const, message: "Output directory is required" };
    if (!(await pathExists(backgroundPath))) return { ok: false as const, message: "Background file does not exist" };
    if (logoPath && !(await pathExists(logoPath))) return { ok: false as const, message: "Logo file does not exist" };

    const detectPython = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
      if (r.ok === false) return null;
      const resolved = String(r.stdout || "").trim();
      if (resolved && existsSync(resolved)) return resolved;
      return cmd;
    };

    const pythonPathStored = String(s.pythonPath || "").trim();
    const pythonPathUsed = (await detectPython(pythonPathStored)) ?? (await detectPython("python")) ?? "";
    if (!pythonPathUsed) return { ok: false as const, message: "Python executable was not found. Set Python path in Settings → Paths." };

    let templateJsonB64 = "";
    try {
      templateJsonB64 = Buffer.from(JSON.stringify(input.template || {}), "utf-8").toString("base64");
    } catch {
      return { ok: false as const, message: "Invalid template data" };
    }

    try {
      await fs.mkdir(outputDir, { recursive: true });
    } catch {
      return { ok: false as const, message: "Could not create output directory" };
    }

    const runId = randomUUID();
    videoRenderRunning = true;

    const send = (evt: VideoRenderEvent) => {
      try { win.webContents.send("mg:videoRenderEvent", evt); } catch {}
    };

    send({ runId, status: "pending", message: `Queued ${mp3Files.length} files for batch export`, progress: 0 });

    setTimeout(async () => {
      try {
        const appPath = app.getAppPath();
        const projectRoot = existsSync(path.join(appPath, "package.json")) ? appPath : process.cwd();
        
        send({ runId, status: "running", message: "Preparing environment...", progress: 0 });
        const env = await ensureVisualizerEnv({
          basePythonPath: pythonPathUsed,
          appPath: projectRoot,
          userDataPath: app.getPath("userData"),
          onStatus: (message) => send({ runId, status: "running", message, progress: 0 }),
        });
        
        if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });
        
        const parseRes = (r: unknown) => {
          const s = String(r || "").trim();
          const m = s.match(/^(\d+)x(\d+)$/);
          const w = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w, h };
        };
        const res = parseRes(s.videoExport?.resolution ?? "1920x1080");
        
        const engine = input.engine === "webgl" ? "webgl" : "python";

        for (let i = 0; i < mp3Files.length; i++) {
          if (videoRenderCancelFlag) {
             send({ runId, status: "failed", message: "Batch export was stopped by user.", progress: 0 });
             break;
          }
          const mp3Path = mp3Files[i];
          const fileName = path.basename(mp3Path);
          const fileStartTs = Date.now();
          
          send({ runId, status: "running", message: `[${i+1}/${mp3Files.length}] Rendering ${fileName}...`, progress: i / mp3Files.length });
          
          const onEvent = (evt: any) => {
            const frame = typeof evt.frame === "number" ? evt.frame : null;
            const totalFrames = typeof evt.totalFrames === "number" ? evt.totalFrames : null;
            let eta = "";
            if (frame && totalFrames && frame > 0 && totalFrames > 0) {
              const elapsedSec = (Date.now() - fileStartTs) / 1000;
              const secPerFrame = elapsedSec / frame;
              const remainSec = Math.max(0, (totalFrames - frame) * secPerFrame);
              const mm = Math.floor(remainSec / 60);
              const ss = Math.floor(remainSec % 60);
              eta = ` ETA ${mm}:${String(ss).padStart(2, "0")}`;
            }
            send({ ...evt, message: `[${i + 1}/${mp3Files.length}] ${evt.message}${eta}` });
          };

          const r =
            engine === "webgl"
              ? await runWebglVideoRender({
                  ffmpegPath: ffmpegPathUsed,
                  exportSettings: s.videoExport,
                  preloadPath: path.join(__dirname, "preload.cjs"),
                  devServerUrl: process.env.VITE_DEV_SERVER_URL,
                  mp3Path,
                  backgroundPath,
                  outputDir,
                  outputName: `${path.basename(mp3Path, path.extname(mp3Path))}.mp4`,
                  logoPath: logoPath || undefined,
                  template: input.template || {},
                  width: res.w,
                  height: res.h,
                  fps: s.videoExport?.fps ?? 30,
                  runId,
                  onEvent,
                  shouldCancel: () => videoRenderCancelFlag,
                })
              : await runVideoRender({
                  pythonPath: env.pythonPath,
                  ffmpegPath: ffmpegPathUsed,
                  appPath: projectRoot,
                  input: {
                    mp3Path,
                    backgroundPath,
                    outputDir,
                    templateJsonB64,
                    logoPath: logoPath || undefined,
                    fps: s.videoExport?.fps ?? 30,
                    width: res.w,
                    height: res.h,
                    renderer: "gpu",
                  },
                  runId,
                  onEvent,
                });
          
          if (r.ok !== true) {
            send({ runId, status: "failed", message: `Failed on ${fileName}: ${r.message}`, progress: 0 });
            return;
          }
        }
        
        send({ runId, status: "done", message: `Successfully exported ${mp3Files.length} videos!`, progress: 1, outputPath: outputDir });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Batch video render failed";
        send({ runId, status: "failed", message: msg, progress: 0 });
      } finally {
        videoRenderRunning = false;
      }
    }, 0);

    return { ok: true as const, runId };
  },
  );

  ipcMain.handle(
    "mg:videoRender:previewPng",
    async (
      _evt,
      input: {
        mp3Path?: string;
        backgroundPath: string;
        templatePath?: string;
        template?: unknown;
        logoPath?: string;
        width?: number;
        height?: number;
        frame?: number;
      },
    ) => {
      if (videoRenderRunning) return { ok: false as const, message: "Video render is already running" };
      try {
        const db = await requireDbCfg();
        await ensureMigrated(db);
        let data = await readAppDataFromDb(db);
        let s = data.settings;

        const probeCmd = async (cmd: string, args: string[]) => {
          return await new Promise<{ ok: true; stdout: string } | { ok: false }>((resolve) => {
            const child = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
            let stdout = "";
            const timer = setTimeout(() => {
              try {
                child.kill();
              } catch {
              }
              resolve({ ok: false });
            }, 3000);
            child.stdout.on("data", (c) => {
              stdout += String(c || "");
            });
            child.on("error", () => {
              clearTimeout(timer);
              resolve({ ok: false });
            });
            child.on("close", (code) => {
              clearTimeout(timer);
              if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") });
              resolve({ ok: false });
            });
          });
        };

        const detectFfmpeg = async (candidate: string) => {
          const cmd = String(candidate || "").trim();
          if (!cmd) return null;
          if (existsSync(cmd)) return cmd;
          const r = await probeCmd(cmd, ["-version"]);
          if (r.ok === false) return null;
          return cmd;
        };

        const ffmpegPathStored = String(s.ffmpegPath || "").trim();
        const ffmpegPathUsed =
          (await detectFfmpeg(ffmpegPathStored)) ??
          (await detectFfmpeg("ffmpeg")) ??
          (await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe")) ??
          (await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe")) ??
          "";
        if (!ffmpegPathUsed) return { ok: false as const, message: "FFmpeg was not found. Set FFmpeg path in Settings → Paths." };

        if (ffmpegPathStored !== ffmpegPathUsed) {
          try {
            data = { ...data, settings: { ...data.settings, ffmpegPath: ffmpegPathUsed } };
            s = data.settings;
            await writeAppDataToDb(db, data);
          } catch {
          }
        }

        const detectPython = async (candidate: string) => {
          const cmd = String(candidate || "").trim();
          if (!cmd) return null;
          const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
          if (r.ok === false) return null;
          const resolved = String(r.stdout || "").trim();
          if (resolved && existsSync(resolved)) return resolved;
          return cmd;
        };

        const pythonPathStored = String(s.pythonPath || "").trim();
        const pythonPathUsed =
          (await detectPython(pythonPathStored)) ?? (await detectPython("py")) ?? (await detectPython("python")) ?? (await detectPython("python3")) ?? "";
        if (!pythonPathUsed) return { ok: false as const, message: "Python executable was not found. Set Python path in Settings → Paths." };

        if (pythonPathStored !== pythonPathUsed) {
          try {
            data = { ...data, settings: { ...data.settings, pythonPath: pythonPathUsed } };
            s = data.settings;
            await writeAppDataToDb(db, data);
          } catch {
          }
        }

        const mp3PathRaw = String(input?.mp3Path || "").trim();
        const backgroundPathRaw = String(input?.backgroundPath || "").trim();
        const backgroundPath = backgroundPathRaw && (await pathExists(backgroundPathRaw)) ? backgroundPathRaw : "";
        if (backgroundPathRaw && !backgroundPath) return { ok: false as const, message: "Background file does not exist" };
        const mp3Path = mp3PathRaw && (await pathExists(mp3PathRaw)) ? mp3PathRaw : "synthetic";

        const templateInline = (input as { template?: unknown }).template;
        const templateId = String(input?.templatePath || s.videoRenderTemplatePath || "").trim();
        let templateJsonB64 = "";
        if (typeof templateInline !== "undefined") {
          templateJsonB64 = Buffer.from(JSON.stringify(templateInline ?? {}), "utf-8").toString("base64");
        } else if (templateId) {
          const tpl = await getVideoTemplate(db, templateId);
          if (tpl) {
            templateJsonB64 = Buffer.from(JSON.stringify(tpl.template ?? {}), "utf-8").toString("base64");
          } else if (templateId.toLowerCase().endsWith(".json") && (await pathExists(templateId))) {
            const raw = await fs.readFile(templateId, "utf-8");
            const parsed = JSON.parse(raw) as unknown;
            templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
          } else {
            return { ok: false as const, message: "Template not found" };
          }
        }

        const previewDir = path.join(app.getPath("userData"), "video-previews");
        await fs.mkdir(previewDir, { recursive: true });
        const outPath = path.join(previewDir, `preview_${Date.now()}.png`);
        const fileUrl = `mgsamples://file?path=${encodeURIComponent(outPath)}`;

        const appPath = app.getAppPath();
        const projectRoot = existsSync(path.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
        if (env.ok === false) return { ok: false as const, message: env.message };

        const parseRes = (r: unknown) => {
          const s2 = String(r || "").trim();
          const m = s2.match(/^(\d+)x(\d+)$/);
          const w = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w, h };
        };
        const baseRes = parseRes(s.videoExport?.resolution ?? "1920x1080");
        const w = Math.max(64, Math.min(1280, Math.floor(Number(input.width ?? 640) || 640)));
        const h = Math.max(64, Math.min(1280, Math.floor(Number(input.height ?? Math.round((w * baseRes.h) / baseRes.w)) || 360)));
        const frame = Math.max(0, Math.floor(Number(input.frame ?? 8) || 8));

        const logoPath = String((input as { logoPath?: string }).logoPath || "").trim();
        const rr = await renderPreviewWithWorker({
          pythonPathUsed,
          projectRoot,
          mp3Path,
          backgroundPath,
          templateJsonB64,
          logoPath,
          fps: s.videoExport?.fps ?? 30,
          width: w,
          height: h,
          frame,
          outPngPath: outPath,
        });
        if (rr.ok === false) {
          await stopPreviewWorker();
          if (String(rr.message || "").toLowerCase().includes("timeout")) {
            return { ok: false as const, message: rr.message };
          }
          const r2 = await runVideoRender({
            pythonPath: env.pythonPath,
            ffmpegPath: ffmpegPathUsed,
            appPath: projectRoot,
            input: {
              mp3Path,
              backgroundPath,
              outputDir: previewDir,
              templateJsonB64: templateJsonB64 || undefined,
              fps: s.videoExport?.fps ?? 30,
              width: w,
              height: h,
              renderer: "gpu",
              previewPngPath: outPath,
              previewFrame: frame,
              logoPath: logoPath || undefined,
            },
            runId: randomUUID(),
            onEvent: () => undefined,
          });
          if (r2.ok !== true) return { ok: false as const, message: rr.message || r2.message };
        }
        return { ok: true as const, filePath: outPath, fileUrl };
      } catch (e) {
        return { ok: false as const, message: e instanceof Error ? e.message : "Preview failed" };
      }
    },
  );

  ipcMain.handle("mg:videoRender:autoLatestBatch", async (_evt, input?: { templatePath?: string }) => {
    if (videoRenderRunning) return { ok: false as const, message: "Video render is already running" };
    const db = await requireDbCfg();
    await ensureMigrated(db);
    let data = await readAppDataFromDb(db);
    let s = data.settings;

    const latest = await getLatestSunoBatchWithOutputDirs(db);
    if (!latest.ok) return { ok: false as const, message: latest.message };
    const okDir = String(latest.okDir || "").trim();
    const altDir = String(latest.altDir || "").trim();
    if (!okDir) return { ok: false as const, message: "No OK run directory found for latest batch" };

    const probeCmd = async (cmd: string, args: string[]) => {
      return await new Promise<{ ok: true; stdout: string } | { ok: false }>((resolve) => {
        const child = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
        let stdout = "";
        const timer = setTimeout(() => {
          try {
            child.kill();
          } catch {
          }
          resolve({ ok: false });
        }, 3000);
        child.stdout.on("data", (c) => {
          stdout += String(c || "");
        });
        child.on("error", () => {
          clearTimeout(timer);
          resolve({ ok: false });
        });
        child.on("close", (code) => {
          clearTimeout(timer);
          if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") });
          resolve({ ok: false });
        });
      });
    };

    const detectFfmpeg = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      if (existsSync(cmd)) return cmd;
      const r = await probeCmd(cmd, ["-version"]);
      if (r.ok === false) return null;
      return cmd;
    };

    const ffmpegPathStored = String(s.ffmpegPath || "").trim();
    const ffmpegPathUsed =
      (await detectFfmpeg(ffmpegPathStored)) ??
      (await detectFfmpeg("ffmpeg")) ??
      (await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe")) ??
      (await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe")) ??
      "";
    if (!ffmpegPathUsed) return { ok: false as const, message: "FFmpeg was not found. Set FFmpeg path in Settings → Paths." };

    if (ffmpegPathStored !== ffmpegPathUsed) {
      try {
        data = { ...data, settings: { ...data.settings, ffmpegPath: ffmpegPathUsed } };
        s = data.settings;
        await writeAppDataToDb(db, data);
      } catch {
      }
    }

    const detectPython = async (candidate: string) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
      if (r.ok === false) return null;
      const resolved = String(r.stdout || "").trim();
      if (resolved && existsSync(resolved)) return resolved;
      return cmd;
    };

    const pythonPathStored = String(s.pythonPath || "").trim();
    const pythonPathUsed =
      (await detectPython(pythonPathStored)) ?? (await detectPython("py")) ?? (await detectPython("python")) ?? (await detectPython("python3")) ?? "";
    if (!pythonPathUsed) return { ok: false as const, message: "Python executable was not found. Set Python path in Settings → Paths." };

    if (pythonPathStored !== pythonPathUsed) {
      try {
        data = { ...data, settings: { ...data.settings, pythonPath: pythonPathUsed } };
        s = data.settings;
        await writeAppDataToDb(db, data);
      } catch {
      }
    }

    const pickTemplateId = String(input?.templatePath ?? s.videoRenderTemplatePath ?? "").trim();
    let templateJsonB64 = "";
    if (pickTemplateId) {
      const tpl = await getVideoTemplate(db, pickTemplateId);
      if (tpl) {
        templateJsonB64 = Buffer.from(JSON.stringify(tpl.template ?? {}), "utf-8").toString("base64");
      } else if (pickTemplateId.toLowerCase().endsWith(".json") && (await pathExists(pickTemplateId))) {
        const raw = await fs.readFile(pickTemplateId, "utf-8");
        const parsed = JSON.parse(raw) as unknown;
        templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
      } else {
        return { ok: false as const, message: "Template not found" };
      }
    }

    const okBg = path.join(okDir, "background.png");
    if (!(await pathExists(okBg))) return { ok: false as const, message: "Batch background.png was not found in OK folder" };
    const okOut = path.join(okDir, "video");

    const dirs: Array<{ dir: string; background: string; outputDir: string; logoPath?: string }> = [];
    const okProfileId = s.activeProfileOkId ?? s.activeProfileId ?? null;
    const okLogo = okProfileId ? data.profiles.find((p) => p.id === okProfileId)?.logoPath ?? "" : "";
    dirs.push({ dir: okDir, background: okBg, outputDir: okOut, logoPath: okLogo || undefined });

    if (altDir && altDir.toLowerCase() !== okDir.toLowerCase()) {
      const altBg = path.join(altDir, "background.png");
      if (!(await pathExists(altBg))) return { ok: false as const, message: "Batch background.png was not found in ALT folder" };
      const altOut = path.join(altDir, "video");
      const altProfileId = s.activeProfileAltId ?? null;
      const altLogo = altProfileId ? data.profiles.find((p) => p.id === altProfileId)?.logoPath ?? "" : "";
      dirs.push({ dir: altDir, background: altBg, outputDir: altOut, logoPath: altLogo || undefined });
    }

    const items: Array<{ mp3Path: string; backgroundPath: string; outputDir: string; logoPath?: string }> = [];
    for (const d of dirs) {
      try {
        const listed = await fs.readdir(d.dir, { withFileTypes: true });
        const mp3s = listed
          .filter((x) => x.isFile() && x.name.toLowerCase().endsWith(".mp3"))
          .map((x) => path.join(d.dir, x.name))
          .sort((a, b) => a.localeCompare(b));
        for (const mp3Path of mp3s) items.push({ mp3Path, backgroundPath: d.background, outputDir: d.outputDir, logoPath: d.logoPath });
      } catch {
        continue;
      }
    }

    if (!items.length) return { ok: false as const, message: "No MP3 files found in latest batch folders" };
    for (const it of items) {
      try {
        await fs.mkdir(it.outputDir, { recursive: true });
      } catch {
        return { ok: false as const, message: "Could not create output directory" };
      }
    }

    const runId = randomUUID();
    videoRenderRunning = true;

    const send = (evt: VideoRenderEvent) => {
      try {
        win.webContents.send("mg:videoRenderEvent", evt);
      } catch {
        return;
      }
    };

    send({ runId, status: "pending", message: `Queued (latest batch: ${latest.batchId})`, progress: 0 });

    setTimeout(async () => {
      try {
        send({ runId, status: "running", message: "Preparing renderer...", progress: 0 });
        const appPath = app.getAppPath();
        const projectRoot = existsSync(path.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnv({
          basePythonPath: pythonPathUsed,
          appPath: projectRoot,
          userDataPath: app.getPath("userData"),
          onStatus: (message) => send({ runId, status: "running", message, progress: 0 }),
        });
        if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });

        const parseRes = (r: unknown) => {
          const s = String(r || "").trim();
          const m = s.match(/^(\d+)x(\d+)$/);
          const w = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w, h };
        };
        const res = parseRes(s.videoExport?.resolution ?? "1920x1080");

        const total = items.length;
        let lastOut = "";
        for (let i = 0; i < items.length; i += 1) {
          const cur = items[i]!;
          const label = path.basename(cur.mp3Path);
          const baseProgress = i / total;
          send({ runId, status: "running", message: `Rendering (${i + 1}/${total}) ${label}`, progress: baseProgress });
          const r = await runVideoRender({
            pythonPath: env.pythonPath,
            ffmpegPath: ffmpegPathUsed,
            appPath: projectRoot,
            input: {
              mp3Path: cur.mp3Path,
              backgroundPath: cur.backgroundPath,
              outputDir: cur.outputDir,
              templateJsonB64: templateJsonB64 || undefined,
              logoPath: cur.logoPath || undefined,
              fps: s.videoExport?.fps ?? 30,
              width: res.w,
              height: res.h,
              renderer: "gpu",
            },
            runId,
            onEvent: (evt) => {
              const inner = typeof evt.progress === "number" ? Math.max(0, Math.min(1, evt.progress)) : 0;
              const combined = (i + inner) / total;
              if (evt.outputPath) lastOut = String(evt.outputPath);
              send({
                runId,
                status: evt.status,
                message: `(${i + 1}/${total}) ${label} — ${evt.message}`,
                progress: combined,
                frame: evt.frame,
                totalFrames: evt.totalFrames,
                outputPath: evt.outputPath,
              });
            },
          });
          if (r.ok === true) lastOut = r.outputPath;
          else return send({ runId, status: "failed", message: r.message, progress: baseProgress });
        }
        send({ runId, status: "done", message: "Done", progress: 1, outputPath: lastOut || undefined });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Video render failed";
        send({ runId, status: "failed", message: msg, progress: 0 });
      } finally {
        videoRenderRunning = false;
      }
    }, 0);

    return { ok: true as const, runId };
  });

  const normalizeVideoTemplateLabel = (input: string) => {
    return String(input || "")
      .trim()
      .replace(/[^a-zA-Z0-9 _.-]+/g, "")
      .replace(/\s+/g, " ")
      .slice(0, 64)
      .trim();
  };



  ipcMain.handle("mg:videoTemplates:list", async () => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const rows = await listVideoTemplates(db);
      const items: VideoTemplateListItem[] = rows.map((r) => ({ label: r.name, path: r.id, source: r.source }));
      items.sort((a, b) => a.label.localeCompare(b.label));
      return { ok: true as const, items };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Template list failed" };
    }
  });

  ipcMain.handle("mg:videoTemplates:read", async (_evt, input: { path: string }) => {
    try {
      const id = String(input?.path || "").trim();
      if (!id) return { ok: false as const, message: "Template ID is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const row = await getVideoTemplate(db, id);
      if (!row) return { ok: false as const, message: "Template not found" };
      return { ok: true as const, template: row.template };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Template read failed" };
    }
  });

  ipcMain.handle("mg:videoTemplates:save", async (_evt, input: { label: string; template: unknown }) => {
    try {
      const label = normalizeVideoTemplateLabel(input?.label || "");
      if (!label) return { ok: false as const, message: "Template name is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const existing = (await listVideoTemplates(db)).find((t) => t.source === "user" && t.name.toLowerCase() === label.toLowerCase()) ?? null;
      const id = existing?.id ?? randomUUID();
      await upsertVideoTemplate(db, { id, name: label, source: "user", template: input?.template ?? {} });
      return { ok: true as const, path: id };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Template save failed" };
    }
  });

  ipcMain.handle("mg:videoTemplates:delete", async (_evt, input: { path: string }) => {
    try {
      const id = String(input?.path || "").trim();
      if (!id) return { ok: false as const, message: "Template ID is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const row = await getVideoTemplate(db, id);
      if (!row) return { ok: false as const, message: "Template not found" };
      if (row.source !== "user") return { ok: false as const, message: "Built-in templates cannot be deleted" };
      await deleteVideoTemplate(db, id);
      return { ok: true as const };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Template delete failed" };
    }
  });


  ipcMain.handle("mg:imageSamples:list", async (_evt, input: { folderPath: string }) => {
    const folderPath = String(input.folderPath || "").trim();
    if (!folderPath) return { ok: false as const, message: "No folder selected" };
    try {
      const items = await listImagesInFolder(folderPath);
      return { ok: true as const, items };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Could not read folder" };
    }
  });

  ipcMain.handle("mg:content:bootstrap", async () => {
    const cfg = await requireDbCfg();
    await ensureMigrated(cfg);
    const res = await bootstrapContent(cfg);
    return { ok: true as const, ...res };
  });

  ipcMain.handle(
    "mg:content:upsert",
    async (_evt, input: ContentUpsertRequest) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      if (input.kind === "promptTemplates") return { ok: true as const, item: await upsertPromptTemplate(cfg, input.item) };
      if (input.kind === "structures") return { ok: true as const, item: await upsertSongStructure(cfg, input.item) };
      if (input.kind === "descriptions") return { ok: true as const, item: await upsertSongDescription(cfg, input.item) };
      if (input.kind === "textStyles") return { ok: true as const, item: await upsertTextStyle(cfg, input.item) };
      if (input.kind === "carModels") return { ok: true as const, item: await upsertCarModel(cfg, input.item) };
      return { ok: false as const, message: "Unknown kind" };
    },
  );

  ipcMain.handle(
    "mg:content:delete",
    async (_evt, input: ContentDeleteRequest) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      if (input.kind === "promptTemplates") return await deletePromptTemplate(cfg, input.id);
      if (input.kind === "structures") return await deleteSongStructure(cfg, input.id);
      if (input.kind === "descriptions") return await deleteSongDescription(cfg, input.id);
      if (input.kind === "textStyles") return await deleteTextStyle(cfg, input.id);
      if (input.kind === "carModels") return await deleteCarModel(cfg, input.id);
      return { ok: false as const, message: "Unknown kind" };
    },
  );

  ipcMain.handle(
    "mg:content:bulkUpsertTextStyles",
    async (_evt, input: ContentBulkUpsertTextStylesRequest) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      const res = await bulkUpsertTextStyles(cfg, input.items);
      return { ok: true as const, ...res };
    },
  );

  ipcMain.handle(
    "mg:content:bulkUpsertCarModels",
    async (_evt, input: ContentBulkUpsertCarModelsRequest) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      const res = await bulkUpsertCarModels(cfg, input.items);
      return { ok: true as const, ...res };
    },
  );


  ipcMain.handle(
    "mg:image:generateBackground",
    async (
      _evt,
      input: {
        prompt: string;
        sampleFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      },
    ) => {
      try {
        console.log("[image] generateBackground start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          sampleFile: path.basename(String(input.sampleFilePath || "")),
          promptChars: String(input.prompt || "").length,
        });
        const db = await requireDbCfg();
        await ensureMigrated(db);
        const data = await readAppDataFromDb(db);
        const apiKey = String(input.apiKey || data.settings.slaiImgApiKey || process.env.SLAI_IMG_API_KEY || "").trim();
        const model = String(data.settings.slaiImgModel || "cgpt-web/gpt-5.5-pro").trim();
        const res = await generateBackgroundWithSlai({
          apiKey,
          model,
          prompt: input.prompt,
          sampleFilePath: input.sampleFilePath,
          resolution: input.resolution,
          outputDir: input.outputDir,
        });
        console.log("[image] generateBackground ok", { filePath: res.filePath, model });
        const outNameRaw = String(input.outputFileName || "").trim();
        if (outNameRaw) {
          const safeNameBase = path.basename(outNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs.mkdir(input.outputDir, { recursive: true });
          const finalPath = path.join(input.outputDir, safeName);
          await fs.copyFile(res.filePath, finalPath);
          const fileUrl = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          return { ok: true as const, filePath: finalPath, fileUrl, meta: res.meta };
        }
        const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
        return { ok: true as const, filePath: res.filePath, fileUrl, meta: res.meta };
      } catch (e) {
        console.error("[image] generateBackground failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false as const, message: e instanceof Error ? e.message : "Image generation failed" };
      }
    },
  );

  ipcMain.handle(
    "mg:image:generateBackgroundPrompt",
    async (
      _evt,
      input: {
        prompt: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      },
    ) => {
      try {
        return { ok: false as const, message: "Prompt-only background generation is disabled. Use sample-based background generation." };
      } catch (e) {
        return { ok: false as const, message: e instanceof Error ? e.message : "Image generation failed" };
      }
    },
  );

  ipcMain.handle(
    "mg:image:generateThumbnail",
    async (
      _evt,
      input: {
        prompt: string;
        backgroundFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      },
    ) => {
      try {
        console.log("[image] generateThumbnail start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          backgroundFile: path.basename(String(input.backgroundFilePath || "")),
          promptChars: String(input.prompt || "").length,
        });
        const db = await requireDbCfg();
        await ensureMigrated(db);
        const data = await readAppDataFromDb(db);
        const apiKey = String(input.apiKey || data.settings.slaiImgApiKey || process.env.SLAI_IMG_API_KEY || "").trim();
        const model = String(data.settings.slaiImgModel || "cgpt-web/gpt-5.5-pro").trim();
        const res = await generateThumbnailWithSlai({
          apiKey,
          model,
          prompt: input.prompt,
          backgroundFilePath: input.backgroundFilePath,
          resolution: input.resolution,
          outputDir: input.outputDir,
        });
        console.log("[image] generateThumbnail ok", { filePath: res.filePath, model });
        const outNameRaw = String(input.outputFileName || "").trim();
        if (outNameRaw) {
          const safeNameBase = path.basename(outNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs.mkdir(input.outputDir, { recursive: true });
          const finalPath = path.join(input.outputDir, safeName);
          await fs.copyFile(res.filePath, finalPath);
          const fileUrl = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          return { ok: true as const, filePath: finalPath, fileUrl, meta: res.meta };
        }

        const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
        return { ok: true as const, filePath: res.filePath, fileUrl, meta: res.meta };
      } catch (e) {
        console.error("[image] generateThumbnail failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false as const, message: e instanceof Error ? e.message : "Thumbnail generation failed" };
      }
    },
  );

  ipcMain.handle(
    "mg:image:generateThumbnailBestOf",
    async (
      _evt,
      input: {
        prompt: string;
        backgroundFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        finalFileName?: string;
        keepCandidates?: boolean;
        apiKey?: string;
        count?: number;
      },
    ) => {
      try {
        console.log("[image] generateThumbnailBestOf start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          backgroundFile: path.basename(String(input.backgroundFilePath || "")),
          promptChars: String(input.prompt || "").length,
          count: input.count,
        });
        const db = await requireDbCfg();
        await ensureMigrated(db);
        const data = await readAppDataFromDb(db);
        const apiKey = String(input.apiKey || data.settings.slaiImgApiKey || process.env.SLAI_IMG_API_KEY || "").trim();
        const model = String(data.settings.slaiImgModel || "cgpt-web/gpt-5.5-pro").trim();
        const count = Math.max(1, Math.min(8, Math.floor(Number(input.count ?? 4) || 4)));
        const candidates: Array<{ filePath: string; fileUrl: string; score: number }> = [];
        for (let i = 0; i < count; i += 1) {
          const res = await generateThumbnailWithSlai({
            apiKey,
            model,
            prompt: input.prompt,
            backgroundFilePath: input.backgroundFilePath,
            resolution: input.resolution,
            outputDir: input.outputDir,
          });
          const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
          const score = scoreImageLumaStddev({ filePath: res.filePath });
          candidates.push({ filePath: res.filePath, fileUrl, score });
        }

        const best = candidates.reduce((a, b) => (b.score > a.score ? b : a), candidates[0]!);
        const finalNameRaw = String(input.finalFileName || "").trim();
        if (finalNameRaw) {
          const safeNameBase = path.basename(finalNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs.mkdir(input.outputDir, { recursive: true });
          const finalPath = path.join(input.outputDir, safeName);
          await fs.copyFile(best.filePath, finalPath);
          const finalUrl = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          if (!input.keepCandidates) {
            await Promise.all(candidates.map((c) => fs.unlink(c.filePath).catch(() => undefined)));
            return { ok: true as const, filePath: finalPath, fileUrl: finalUrl, candidates: [] };
          }
          return { ok: true as const, filePath: finalPath, fileUrl: finalUrl, candidates };
        }

        return { ok: true as const, filePath: best.filePath, fileUrl: best.fileUrl, candidates };
      } catch (e) {
        console.error("[image] generateThumbnailBestOf failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false as const, message: e instanceof Error ? e.message : "Thumbnail generation failed" };
      }
    },
  );

  ipcMain.handle(
    "mg:image:listGenerated",
    async (
      _evt,
      input: {
        outputDir: string;
        kind: "background" | "thumbnail";
        limit?: number;
      },
    ) => {
      try {
        const root = String(input.outputDir || "").trim();
        if (!root) return { ok: false as const, message: "Output directory is required" };

        const kind = input.kind === "thumbnail" ? "thumbnail" : "background";
        const limit = Math.max(1, Math.min(200, Math.floor(Number(input.limit ?? 50) || 50)));

        const items: Array<{ filePath: string; fileUrl: string; mtimeMs: number }> = [];

        const currentName = kind === "background" ? "background.png" : "thumbnail.png";
        const currentPath = path.join(root, currentName);
        try {
          const st = await fs.stat(currentPath);
          if (st.isFile()) {
            items.push({
              filePath: currentPath,
              fileUrl: `mgsamples://file?path=${encodeURIComponent(currentPath)}`,
              mtimeMs: st.mtimeMs,
            });
          }
        } catch {
        }

        const dirName = kind === "background" ? "backgrounds" : "thumbnails";
        const dirPath = path.join(root, dirName);
        let names: string[] = [];
        try {
          names = await fs.readdir(dirPath);
        } catch {
          names = [];
        }

        const rows: Array<{ filePath: string; mtimeMs: number }> = [];
        for (const name of names) {
          if (!name.toLowerCase().endsWith(".png")) continue;
          const fp = path.join(dirPath, name);
          try {
            const st = await fs.stat(fp);
            if (!st.isFile()) continue;
            rows.push({ filePath: fp, mtimeMs: st.mtimeMs });
          } catch {
            continue;
          }
        }

        rows.sort((a, b) => b.mtimeMs - a.mtimeMs);
        for (const r of rows.slice(0, limit)) {
          items.push({
            filePath: r.filePath,
            fileUrl: `mgsamples://file?path=${encodeURIComponent(r.filePath)}`,
            mtimeMs: r.mtimeMs,
          });
        }

        const seen = new Set<string>();
        const uniq = items.filter((x) => {
          if (seen.has(x.filePath)) return false;
          seen.add(x.filePath);
          return true;
        });

        uniq.sort((a, b) => b.mtimeMs - a.mtimeMs);
        return { ok: true as const, items: uniq.slice(0, limit) };
      } catch (e) {
        return { ok: false as const, message: e instanceof Error ? e.message : "Failed to list images" };
      }
    },
  );

  ipcMain.handle(
    "mg:db:testConnection",
    async (_evt, cfg: { host: string; port: number; user: string; password: string; database: string }) => {
      return await testPostgresConnection({
        host: cfg.host,
        port: cfg.port,
        user: cfg.user,
        password: cfg.password,
        database: cfg.database,
        timeoutMs: 6000,
      });
    },
  );

  ipcMain.handle(
    "mg:db:ensureAndMigrate",
    async (_evt, cfg: { host: string; port: number; user: string; password: string; database: string }) => {
      return await ensureDatabaseAndMigrate(cfg);
    },
  );

  ipcMain.handle(
    "mg:pools:stats",
    async (_evt, cfg: { host: string; port: number; user: string; password: string; database: string }) => {
      await ensureMigrated(cfg);
      return await poolStats(cfg);
    },
  );

  ipcMain.handle(
    "mg:pools:import",
    async (
      _evt,
      input: {
        kind: "titles" | "albums" | "openings";
        filePath: string;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      },
    ) => {
      await ensureMigrated(input.cfg);
      const raw = await fs.readFile(input.filePath, "utf-8");
      if (input.kind === "titles") {
        const lines = raw.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
        return await importTitles(input.cfg, lines);
      }
      if (input.kind === "albums") {
        const lines = raw.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
        return await importAlbums(input.cfg, lines);
      }

      const pairs: Array<{ line1: string; line2: string }> = [];
      const lines = raw.split(/\r?\n/);
      for (const line of lines) {
        const t = line.trim();
        if (!t) continue;
        const sep = t.includes("\t") ? "\t" : t.includes("|") ? "|" : null;
        if (sep) {
          const [a, b] = t.split(sep).map((x) => x.trim());
          if (a && b) pairs.push({ line1: a, line2: b });
        } else {
          const last = pairs[pairs.length - 1];
          if (!last || (last.line1 && last.line2)) pairs.push({ line1: t, line2: "" });
          else last.line2 = t;
        }
      }
      return await importOpenings(input.cfg, pairs.filter((p) => p.line1 && p.line2));
    },
  );

  ipcMain.handle(
    "mg:pools:list",
    async (
      _evt,
      input: {
        kind: "titles" | "albums" | "openings";
        limit: number;
        offset: number;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      },
    ) => {
      await ensureMigrated(input.cfg);
      return await listPool(input.cfg, { kind: input.kind, limit: input.limit, offset: input.offset });
    },
  );

  ipcMain.handle(
    "mg:pools:generate",
    async (
      _evt,
      input: {
        kind: "titles" | "albums" | "openings";
        count: number;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      },
    ) => {
      await ensureMigrated(input.cfg);
      return await generateAndInsert(input.cfg, { kind: input.kind, count: input.count });
    },
  );

  ipcMain.handle(
    "mg:pools:clear",
    async (
      _evt,
      input: {
        kind: "titles" | "albums" | "openings";
        cfg: { host: string; port: number; user: string; password: string; database: string };
      },
    ) => {
      await ensureMigrated(input.cfg);
      return await clearPool(input.cfg, input.kind);
    },
  );

  ipcMain.handle(
    "mg:db:clearGenerated",
    async (_evt, cfg: { host: string; port: number; user: string; password: string; database: string }) => {
      await ensureMigrated(cfg);
      return await clearGenerated(cfg);
    },
  );

  ipcMain.handle("mg:ffmpeg:download", async (_evt, opts: { installDir: string }) => {
    return await downloadFfmpeg(opts);
  });

  ipcMain.handle("mg:lyrics:polish", async (_evt, input: { lyrics: string; strength: number; apiKey?: string }) => {
    const apiKey = input.apiKey || process.env.OPENAI_API_KEY;
    if (!apiKey) return { ok: false as const, message: "OpenAI API key is not configured" };
    try {
      const lyrics = await polishLyricsWithOpenAI({ apiKey, lyrics: input.lyrics, strength: input.strength });
      return { ok: true as const, lyrics };
    } catch (e) {
      return { ok: false as const, message: e instanceof Error ? e.message : "Polish failed" };
    }
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", async () => {
  try {
    await ngrok.stop();
  } catch {
    // ignore
  }
  try {
    await callbackServer?.close();
  } catch {
    // ignore
  }
});

