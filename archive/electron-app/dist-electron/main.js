// electron/main.ts
import { app as app2, BrowserWindow as BrowserWindow2, Menu, dialog, ipcMain as ipcMain3, shell, protocol } from "electron";
import path13 from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync as existsSync3 } from "node:fs";
import { randomUUID as randomUUID4 } from "node:crypto";
import { spawn as spawn7 } from "node:child_process";

// electron/storage.ts
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
var DATA_FILE_NAME = "mg-data.json";
var SETTINGS_FILE_NAME = "settings.json";
var LEGACY_SETTINGS_FILE_NAME = "mg-settings.json";
function nowIso() {
  return (/* @__PURE__ */ new Date()).toISOString();
}
function createDefaultData() {
  const updatedAt = nowIso();
  return {
    descriptions: [
      {
        id: "desc-01",
        name: "01",
        content: "High-energy Eurodance and Hands Up track featuring a blend of English vocals. The song is set in a minor key at 142 BPM. It opens with a heavy four-on-the-floor kick drum and a syncopated, buzzy synth bassline.",
        updatedAt
      }
    ],
    structures: [
      {
        id: "struct-01",
        name: "Festival",
        content: "[Intro: kick + hi-hat groove, DJ friendly]\n[Groove: bassline enters, simple rhythm]\n[Build: add percussion layers]\n[Drop: full groove, catchy bassline hook]\n[Break: remove drums, filtered elements]\n[Build: reintroduce rhythm]\n[Drop: same groove with variation]\n[Outro: strip back for mixing]",
        updatedAt
      }
    ],
    songs: [],
    songDrafts: [
      { id: "draft-01", title: "", album: "" }
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
      sunoTimeoutMs: 9e4,
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
      dbName: "MG"
    }
  };
}
function getDataFilePath(userDataDir) {
  return path.join(userDataDir, DATA_FILE_NAME);
}
function getSettingsFilePath(userDataDir) {
  return path.join(userDataDir, SETTINGS_FILE_NAME);
}
function getLegacySettingsFilePath(userDataDir) {
  return path.join(userDataDir, LEGACY_SETTINGS_FILE_NAME);
}
async function readSettings(settingsFilePath) {
  try {
    const raw = await fs.readFile(settingsFilePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
async function writeSettings(settingsFilePath, settings) {
  await writeJsonAtomically(settingsFilePath, settings);
}
async function readBestSettings(settingsFilePath, legacySettingsFilePath) {
  const settings = await readSettings(settingsFilePath);
  if (settings) return settings;
  const legacy = await readSettings(legacySettingsFilePath);
  if (legacy) {
    await writeSettings(settingsFilePath, legacy);
    return legacy;
  }
  return null;
}
async function writeJsonAtomically(filePath, data) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(data, null, 2), "utf-8");
  for (let i = 0; i < 12; i += 1) {
    try {
      await fs.rename(tmp, filePath);
      return;
    } catch (e) {
      const code = e?.code;
      const retryable = code === "EPERM" || code === "EBUSY" || code === "EACCES";
      if (!retryable) throw e;
      await new Promise((r) => setTimeout(r, 35 * (i + 1)));
    }
  }
  await fs.rename(tmp, filePath);
}
var writeChain = Promise.resolve();
function stamp() {
  const d = /* @__PURE__ */ new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${yyyy}${mm}${dd}-${hh}${mi}${ss}`;
}
async function readAppData(dataFilePath) {
  const userDataDir = path.dirname(dataFilePath);
  const settingsFilePath = getSettingsFilePath(userDataDir);
  const legacySettingsFilePath = getLegacySettingsFilePath(userDataDir);
  try {
    const raw = await fs.readFile(dataFilePath, "utf-8");
    let parsed;
    try {
      parsed = JSON.parse(raw);
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
async function writeAppData(dataFilePath, data) {
  writeChain = writeChain.catch(() => void 0).then(async () => {
    const settingsFilePath = getSettingsFilePath(path.dirname(dataFilePath));
    await writeSettings(settingsFilePath, data.settings);
    await writeJsonAtomically(dataFilePath, data);
  });
  await writeChain;
}

// electron/main.ts
import { format } from "node:util";

// electron/jobQueue.ts
import { EventEmitter } from "node:events";
import { randomUUID as randomUUID2 } from "node:crypto";
import path4 from "node:path";

// electron/ffmpegMerge.ts
import { promises as fs2 } from "node:fs";
import path2 from "node:path";
import { spawn } from "node:child_process";
function nowStamp() {
  const d = /* @__PURE__ */ new Date();
  const p = (n) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}
function isAudioFile(fileName) {
  const lower = fileName.toLowerCase();
  return lower.endsWith(".mp3") || lower.endsWith(".wav") || lower.endsWith(".m4a");
}
function classify(fileName) {
  const base = fileName.toUpperCase();
  if (base.includes("_ALT") || base.includes("-ALT")) return "ALT";
  return "OK";
}
function chunk(items, size) {
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}
async function runFfmpegConcat(ffmpegPath, listFilePath, outPath) {
  await new Promise((resolve, reject) => {
    const child = spawn(ffmpegPath, ["-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", listFilePath, "-c", "copy", outPath], {
      windowsHide: true
    });
    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || `ffmpeg exited with code ${code ?? -1}`));
    });
  });
}
async function mergeAudioByVersion(req) {
  if (!Number.isFinite(req.chunkSize) || req.chunkSize < 0) throw new Error("chunkSize must be >= 0");
  const entries = await fs2.readdir(req.inputDir, { withFileTypes: true });
  const files = entries.filter((e) => e.isFile()).map((e) => e.name).filter(isAudioFile).map((name) => ({
    name,
    fullPath: path2.resolve(req.inputDir, name),
    version: classify(name)
  }));
  const okFiles = files.filter((f) => f.version === "OK");
  const altFiles = files.filter((f) => f.version === "ALT");
  const selected = req.versionType === "OK" ? okFiles : altFiles;
  await fs2.mkdir(req.outputDir, { recursive: true });
  const stamp2 = nowStamp();
  const effectiveChunkSize = req.chunkSize === 0 ? selected.length : req.chunkSize;
  const chunks = chunk(selected, Math.max(1, effectiveChunkSize));
  const outputFiles = [];
  for (let i = 0; i < chunks.length; i++) {
    const listContent = chunks[i].map((f) => {
      const safe = f.fullPath.replace(/'/g, "'\\''");
      return `file '${safe}'`;
    }).join("\n");
    const listFilePath = path2.resolve(req.outputDir, `concat_${req.versionType}_${stamp2}_${i + 1}.txt`);
    await fs2.writeFile(listFilePath, listContent, "utf-8");
    const outPath = path2.resolve(req.outputDir, `merged_${req.versionType}_${stamp2}_${i + 1}.mp3`);
    await runFfmpegConcat(req.ffmpegPath, listFilePath, outPath);
    outputFiles.push(outPath);
  }
  return {
    outputFiles,
    inputCounts: {
      OK: okFiles.length,
      ALT: altFiles.length
    }
  };
}

// electron/ai/deepseekSong.ts
function extractJson(text) {
  const s = String(text || "");
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end < 0 || end <= start) return null;
  try {
    return JSON.parse(s.slice(start, end + 1));
  } catch {
    return null;
  }
}
async function chatCompletion(input) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 9e4);
  const res = await fetch("https://api.deepseek.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${input.apiKey}`
    },
    body: JSON.stringify({
      model: input.model,
      temperature: input.temperature,
      messages: input.messages,
      stream: false
    }),
    signal: controller.signal
  }).finally(() => clearTimeout(t));
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`DeepSeek error ${res.status}: ${body.slice(0, 400)}`);
  }
  const json = await res.json();
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("DeepSeek returned empty content");
  return content;
}
function normalize(s) {
  return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
}
function opening2(lyrics) {
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "").split("\n").map((x) => x.trim()).filter((l) => l && !isHeader(l)).slice(0, 2);
  return lines.join("\n");
}
function lyricStats(lyrics) {
  const lines = String(lyrics || "").split("\n").map((x) => x.trim());
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const contentLines = lines.filter((l) => l && !isHeader(l));
  const headers = lines.filter((l) => l && isHeader(l));
  const headerText = headers.map((h) => h.toLowerCase());
  const count = (needle) => headerText.filter((h) => h.includes(needle)).length;
  return {
    contentLineCount: contentLines.length,
    headerCount: headers.length,
    verseCount: count("verse"),
    chorusCount: count("chorus"),
    bridgeCount: count("bridge")
  };
}
function injectOpening(lyrics, opening) {
  const want = String(opening || "").split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 2);
  if (want.length < 2) return lyrics;
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l.trim());
  const lines = String(lyrics || "").split("\n");
  const out = [];
  let replaced = 0;
  for (const line of lines) {
    if (replaced < 2 && line.trim() && !isHeader(line)) {
      out.push(want[replaced] ?? line);
      replaced += 1;
    } else {
      out.push(line);
    }
  }
  if (replaced < 2) return `${want.join("\n")}

${String(lyrics || "").trim()}`;
  return out.join("\n");
}
function parseStructureHeaders(structure) {
  const headers = String(structure || "").split("\n").map((l) => l.trim()).filter(Boolean).filter((l) => /^\[[^\]]+\]$/.test(l));
  return headers;
}
function extractHeadersInLyrics(lyrics) {
  return String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean).filter((l) => /^\[[^\]]+\]$/.test(l));
}
function hasContentBeforeFirstHeader(lyrics) {
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "").split("\n").map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (isHeader(l)) return false;
    return true;
  }
  return false;
}
async function generateSongDraftWithDeepSeek(input) {
  const model = input.model ?? "deepseek-chat";
  const avoidTitles = (input.avoidTitles ?? []).filter(Boolean).slice(0, 120);
  const avoidAlbums = (input.avoidAlbums ?? []).filter(Boolean).slice(0, 120);
  const avoidOpenings = (input.avoidOpenings ?? []).filter(Boolean).slice(0, 120);
  const strictLevel = input.strictLevel ?? 3;
  const uniqueOpening = Boolean(input.uniqueOpening);
  const avoidTitleSet = new Set(avoidTitles.map(normalize).filter(Boolean));
  const avoidAlbumSet = new Set(avoidAlbums.map(normalize).filter(Boolean));
  const avoidOpeningSet = new Set(avoidOpenings.map(normalize).filter(Boolean));
  const forcedTitle = String(input.forcedTitle || "").trim();
  const forcedAlbum = String(input.forcedAlbum || "").trim();
  const forcedOpening = String(input.forcedOpening || "").trim();
  const expectedHeaders = parseStructureHeaders(input.structure || "");
  const minContentLines = expectedHeaders.length ? Math.max(16, expectedHeaders.length * 4) : 32;
  const rejectLog = [];
  const pushReject = (attempt, reason) => {
    rejectLog.push(`#${attempt} ${reason}`);
    if (rejectLog.length > 24) rejectLog.shift();
  };
  const avoidBlock = [];
  if (strictLevel >= 2 && avoidTitles.length) avoidBlock.push(`Forbidden titles (avoid exact repeats):
- ${avoidTitles.join("\n- ")}`);
  if (strictLevel >= 3 && avoidAlbums.length) avoidBlock.push(`Forbidden album names (avoid exact repeats):
- ${avoidAlbums.join("\n- ")}`);
  if ((strictLevel >= 1 || uniqueOpening) && avoidOpenings.length)
    avoidBlock.push(`Forbidden lyric openings (first two lines; avoid exact repeats):
- ${avoidOpenings.join("\n- ")}`);
  const maxAttempts = 12;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const fixed = [];
    if (forcedTitle) fixed.push(`- Use EXACT title: ${forcedTitle}`);
    if (forcedAlbum) fixed.push(`- Use EXACT album name: ${forcedAlbum}`);
    if (forcedOpening) fixed.push(`- The first two non-empty lyric lines must be EXACTLY:
${forcedOpening}`);
    let raw = "";
    try {
      raw = await chatCompletion({
        apiKey: input.apiKey,
        model,
        temperature: Math.min(1.2, Math.max(0.2, input.creativity / 85)),
        messages: [
          {
            role: "system",
            content: "You generate music metadata and lyrics. Output MUST be strict JSON with keys: title, album, lyrics. No markdown, no extra text."
          },
          {
            role: "user",
            content: [
              `Attempt: ${attempt}/${maxAttempts}`,
              `Language: ${input.language}`,
              `Creativity: ${input.creativity}/100`,
              "Song description:",
              input.description || "(empty)",
              "Song structure:",
              input.structure || "(empty)",
              avoidBlock.length ? "Avoid list:" : "",
              avoidBlock.length ? avoidBlock.join("\n\n") : "",
              fixed.length ? "Fixed values:" : "",
              fixed.length ? fixed.join("\n") : "",
              "Constraints:",
              expectedHeaders.length ? [
                "- Use EXACT section headers and EXACT order from Song structure (one header per line)",
                ...expectedHeaders.map((h) => `  ${h}`),
                "- Do NOT add Intro/Outro unless Song structure includes them",
                "- Do NOT add any extra section headers that are not in Song structure",
                "- Do NOT write any lyrics before the first header"
              ].join("\n") : "- Lyrics must include section labels like [Verse], [Chorus], [Bridge]",
              "- Write a FULL song, not a sketch",
              "- Each section should have 4-8 lyric lines (excluding section labels)",
              `- Total non-empty lyric lines (excluding section labels) must be at least ${minContentLines}`,
              "- Title should be short and catchy",
              "- Album name should be plausible",
              "- Do NOT output any forbidden exact titles/albums/openings",
              "- The first two non-empty lyric lines must be distinctive"
            ].join("\n")
          }
        ]
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      pushReject(attempt, `api_error: ${msg}`);
      continue;
    }
    const parsed = extractJson(raw);
    if (!parsed?.title || !parsed?.album || !parsed?.lyrics) {
      pushReject(attempt, "bad_json_or_missing_keys");
      continue;
    }
    const title = forcedTitle || String(parsed.title).trim();
    const album = forcedAlbum || String(parsed.album).trim();
    const lyrics = forcedOpening ? injectOpening(String(parsed.lyrics), forcedOpening) : String(parsed.lyrics);
    const stats = lyricStats(lyrics);
    if (stats.contentLineCount < minContentLines) {
      pushReject(attempt, `too_short: contentLines=${stats.contentLineCount} min=${minContentLines}`);
      continue;
    }
    if (expectedHeaders.length) {
      if (hasContentBeforeFirstHeader(lyrics)) {
        const firstLine = String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean)[0];
        pushReject(attempt, `content_before_first_header: firstLine=${JSON.stringify(firstLine || "")}`);
        continue;
      }
      const gotHeaders = extractHeadersInLyrics(lyrics);
      if (gotHeaders.length !== expectedHeaders.length) {
        const got = gotHeaders.slice(0, 10).join(" ");
        const exp = expectedHeaders.slice(0, 10).join(" ");
        pushReject(attempt, `header_count_mismatch: got=${gotHeaders.length} expected=${expectedHeaders.length} gotHeaders=${JSON.stringify(got)} expectedHeaders=${JSON.stringify(exp)}`);
        continue;
      }
      let mismatch = false;
      let mismatchAt = -1;
      for (let i = 0; i < expectedHeaders.length; i += 1) {
        if (String(gotHeaders[i] || "").trim() !== String(expectedHeaders[i] || "").trim()) {
          mismatch = true;
          mismatchAt = i;
          break;
        }
      }
      if (mismatch) {
        pushReject(
          attempt,
          `header_mismatch_at=${mismatchAt}: got=${JSON.stringify(String(gotHeaders[mismatchAt] || ""))} expected=${JSON.stringify(String(expectedHeaders[mismatchAt] || ""))}`
        );
        continue;
      }
      const firstNonEmpty = String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean)[0];
      if (firstNonEmpty && firstNonEmpty !== expectedHeaders[0]) {
        pushReject(attempt, `first_line_not_first_header: firstLine=${JSON.stringify(firstNonEmpty)} expectedFirstHeader=${JSON.stringify(expectedHeaders[0])}`);
        continue;
      }
    }
    const violatesOpening = (strictLevel >= 1 || uniqueOpening) && avoidOpeningSet.has(normalize(opening2(lyrics)));
    const violatesTitle = strictLevel >= 2 && avoidTitleSet.has(normalize(title));
    const violatesAlbum = strictLevel >= 3 && avoidAlbumSet.has(normalize(album));
    if (violatesOpening || violatesTitle || violatesAlbum) {
      const parts = [];
      if (violatesTitle) parts.push("duplicate_title");
      if (violatesAlbum) parts.push("duplicate_album");
      if (violatesOpening) parts.push("duplicate_opening");
      pushReject(attempt, `avoid_list_violation: ${parts.join(",")}`);
      continue;
    }
    return {
      title,
      album,
      lyricsRaw: String(lyrics).trim()
    };
  }
  const tail = rejectLog.slice(-8).join(" | ");
  throw new Error(`DeepSeek draft rejected after ${maxAttempts} tries. Recent reasons: ${tail || "(no details)"}`);
}

// electron/ai/slaiSong.ts
function extractJson2(text) {
  const s = String(text || "");
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end < 0 || end <= start) return null;
  try {
    return JSON.parse(s.slice(start, end + 1));
  } catch {
    return null;
  }
}
async function chatCompletion2(input) {
  const startedAt = Date.now();
  console.log("[slaiSong] chat.completions start", { model: input.model, temperature: input.temperature, messageCount: input.messages.length });
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 9e4);
  const res = await fetch("https://api.slai.shop/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${input.apiKey}`
    },
    body: JSON.stringify({
      model: input.model,
      temperature: input.temperature,
      messages: input.messages,
      stream: false
    }),
    signal: controller.signal
  }).finally(() => clearTimeout(t));
  const ms = Date.now() - startedAt;
  console.log("[slaiSong] chat.completions response", { status: res.status, ok: res.ok, ms });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    console.log("[slaiSong] chat.completions error body", { status: res.status, bodyPreview: body.slice(0, 220) });
    throw new Error(`SLAI error ${res.status}: ${body.slice(0, 400)}`);
  }
  const json = await res.json();
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("SLAI returned empty content");
  console.log("[slaiSong] chat.completions done", { ms: Date.now() - startedAt, contentChars: content.length });
  return content;
}
function normalize2(s) {
  return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
}
function opening22(lyrics) {
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "").split("\n").map((x) => x.trim()).filter((l) => l && !isHeader(l)).slice(0, 2);
  return lines.join("\n");
}
function lyricStats2(lyrics) {
  const lines = String(lyrics || "").split("\n").map((x) => x.trim());
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const contentLines = lines.filter((l) => l && !isHeader(l));
  const headers = lines.filter((l) => l && isHeader(l));
  const headerText = headers.map((h) => h.toLowerCase());
  const count = (needle) => headerText.filter((h) => h.includes(needle)).length;
  return {
    contentLineCount: contentLines.length,
    headerCount: headers.length,
    verseCount: count("verse"),
    chorusCount: count("chorus"),
    bridgeCount: count("bridge")
  };
}
function injectOpening2(lyrics, opening) {
  const want = String(opening || "").split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 2);
  if (want.length < 2) return lyrics;
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l.trim());
  const lines = String(lyrics || "").split("\n");
  const out = [];
  let replaced = 0;
  for (const line of lines) {
    if (replaced < 2 && line.trim() && !isHeader(line)) {
      out.push(want[replaced] ?? line);
      replaced += 1;
    } else {
      out.push(line);
    }
  }
  if (replaced < 2) return `${want.join("\n")}

${String(lyrics || "").trim()}`;
  return out.join("\n");
}
function parseStructureHeaders2(structure) {
  const headers = String(structure || "").split("\n").map((l) => l.trim()).filter(Boolean).filter((l) => /^\[[^\]]+\]$/.test(l));
  return headers;
}
function extractHeadersInLyrics2(lyrics) {
  return String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean).filter((l) => /^\[[^\]]+\]$/.test(l));
}
function hasContentBeforeFirstHeader2(lyrics) {
  const isHeader = (l) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "").split("\n").map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (isHeader(l)) return false;
    return true;
  }
  return false;
}
async function generateSongDraftWithSlai(input) {
  const model = String(input.model || "").trim() || "gpt-5.5";
  const avoidTitles = (input.avoidTitles ?? []).filter(Boolean).slice(0, 120);
  const avoidAlbums = (input.avoidAlbums ?? []).filter(Boolean).slice(0, 120);
  const avoidOpenings = (input.avoidOpenings ?? []).filter(Boolean).slice(0, 120);
  const strictLevel = input.strictLevel ?? 3;
  const uniqueOpening = Boolean(input.uniqueOpening);
  const avoidTitleSet = new Set(avoidTitles.map(normalize2).filter(Boolean));
  const avoidAlbumSet = new Set(avoidAlbums.map(normalize2).filter(Boolean));
  const avoidOpeningSet = new Set(avoidOpenings.map(normalize2).filter(Boolean));
  const forcedTitle = String(input.forcedTitle || "").trim();
  const forcedAlbum = String(input.forcedAlbum || "").trim();
  const forcedOpening = String(input.forcedOpening || "").trim();
  const expectedHeaders = parseStructureHeaders2(input.structure || "");
  const minContentLines = expectedHeaders.length ? Math.max(16, expectedHeaders.length * 4) : 32;
  const rejectLog = [];
  const pushReject = (attempt, reason) => {
    rejectLog.push(`#${attempt} ${reason}`);
    if (rejectLog.length > 24) rejectLog.shift();
  };
  const avoidBlock = [];
  if (strictLevel >= 2 && avoidTitles.length) avoidBlock.push(`Forbidden titles (avoid exact repeats):
- ${avoidTitles.join("\n- ")}`);
  if (strictLevel >= 3 && avoidAlbums.length) avoidBlock.push(`Forbidden album names (avoid exact repeats):
- ${avoidAlbums.join("\n- ")}`);
  if ((strictLevel >= 1 || uniqueOpening) && avoidOpenings.length)
    avoidBlock.push(`Forbidden lyric openings (first two lines; avoid exact repeats):
- ${avoidOpenings.join("\n- ")}`);
  const maxAttempts = 12;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const fixed = [];
    if (forcedTitle) fixed.push(`- Use EXACT title: ${forcedTitle}`);
    if (forcedAlbum) fixed.push(`- Use EXACT album name: ${forcedAlbum}`);
    if (forcedOpening) fixed.push(`- The first two non-empty lyric lines must be EXACTLY:
${forcedOpening}`);
    let raw = "";
    try {
      raw = await chatCompletion2({
        apiKey: input.apiKey,
        model,
        temperature: Math.min(1.2, Math.max(0.2, input.creativity / 85)),
        messages: [
          {
            role: "system",
            content: "You generate music metadata and lyrics. Output MUST be strict JSON with keys: title, album, lyrics. No markdown, no extra text."
          },
          {
            role: "user",
            content: [
              `Attempt: ${attempt}/${maxAttempts}`,
              `Language: ${input.language}`,
              `Creativity: ${input.creativity}/100`,
              "Song description:",
              input.description || "(empty)",
              "Song structure:",
              input.structure || "(empty)",
              avoidBlock.length ? "Avoid list:" : "",
              avoidBlock.length ? avoidBlock.join("\n\n") : "",
              fixed.length ? "Fixed values:" : "",
              fixed.length ? fixed.join("\n") : "",
              "Constraints:",
              expectedHeaders.length ? [
                "- Use EXACT section headers and EXACT order from Song structure (one header per line)",
                ...expectedHeaders.map((h) => `  ${h}`),
                "- Do NOT add Intro/Outro unless Song structure includes them",
                "- Do NOT add any extra section headers that are not in Song structure",
                "- Do NOT write any lyrics before the first header"
              ].join("\n") : "- Lyrics must include section labels like [Verse], [Chorus], [Bridge]",
              "- Write a FULL song, not a sketch",
              "- Each section should have 4-8 lyric lines (excluding section labels)",
              `- Total non-empty lyric lines (excluding section labels) must be at least ${minContentLines}`,
              "- Title should be short and catchy",
              "- Album name should be plausible",
              "- Do NOT output any forbidden exact titles/albums/openings",
              "- The first two non-empty lyric lines must be distinctive"
            ].join("\n")
          }
        ]
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      pushReject(attempt, `api_error: ${msg}`);
      continue;
    }
    const parsed = extractJson2(raw);
    if (!parsed?.title || !parsed?.album || !parsed?.lyrics) {
      pushReject(attempt, "bad_json_or_missing_keys");
      continue;
    }
    const title = forcedTitle || String(parsed.title).trim();
    const album = forcedAlbum || String(parsed.album).trim();
    const lyrics = forcedOpening ? injectOpening2(String(parsed.lyrics), forcedOpening) : String(parsed.lyrics);
    const stats = lyricStats2(lyrics);
    if (stats.contentLineCount < minContentLines) {
      pushReject(attempt, `too_short: contentLines=${stats.contentLineCount} min=${minContentLines}`);
      continue;
    }
    if (expectedHeaders.length) {
      if (hasContentBeforeFirstHeader2(lyrics)) {
        const firstLine = String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean)[0];
        pushReject(attempt, `content_before_first_header: firstLine=${JSON.stringify(firstLine || "")}`);
        continue;
      }
      const gotHeaders = extractHeadersInLyrics2(lyrics);
      if (gotHeaders.length !== expectedHeaders.length) {
        const got = gotHeaders.slice(0, 10).join(" ");
        const exp = expectedHeaders.slice(0, 10).join(" ");
        pushReject(
          attempt,
          `header_count_mismatch: got=${gotHeaders.length} expected=${expectedHeaders.length} gotHeaders=${JSON.stringify(got)} expectedHeaders=${JSON.stringify(exp)}`
        );
        continue;
      }
      let mismatch = false;
      let mismatchAt = -1;
      for (let i = 0; i < expectedHeaders.length; i += 1) {
        if (String(gotHeaders[i] || "").trim() !== String(expectedHeaders[i] || "").trim()) {
          mismatch = true;
          mismatchAt = i;
          break;
        }
      }
      if (mismatch) {
        pushReject(
          attempt,
          `header_mismatch_at=${mismatchAt}: got=${JSON.stringify(String(gotHeaders[mismatchAt] || ""))} expected=${JSON.stringify(String(expectedHeaders[mismatchAt] || ""))}`
        );
        continue;
      }
      const firstNonEmpty = String(lyrics || "").split("\n").map((l) => l.trim()).filter(Boolean)[0];
      if (firstNonEmpty && firstNonEmpty !== expectedHeaders[0]) {
        pushReject(
          attempt,
          `first_line_not_first_header: firstLine=${JSON.stringify(firstNonEmpty)} expectedFirstHeader=${JSON.stringify(expectedHeaders[0])}`
        );
        continue;
      }
    }
    const violatesOpening = (strictLevel >= 1 || uniqueOpening) && avoidOpeningSet.has(normalize2(opening22(lyrics)));
    const violatesTitle = strictLevel >= 2 && avoidTitleSet.has(normalize2(title));
    const violatesAlbum = strictLevel >= 3 && avoidAlbumSet.has(normalize2(album));
    if (violatesOpening || violatesTitle || violatesAlbum) {
      const parts = [];
      if (violatesTitle) parts.push("duplicate_title");
      if (violatesAlbum) parts.push("duplicate_album");
      if (violatesOpening) parts.push("duplicate_opening");
      pushReject(attempt, `avoid_list_violation: ${parts.join(",")}`);
      continue;
    }
    return {
      title,
      album,
      lyricsRaw: String(lyrics).trim()
    };
  }
  const tail = rejectLog.slice(-8).join(" | ");
  throw new Error(`SLAI draft rejected after ${maxAttempts} tries. Recent reasons: ${tail || "(no details)"}`);
}

// electron/db/phrasePools.ts
import * as pg from "pg";

// electron/db/poolGenerators.ts
function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
function normalize3(text) {
  return String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
}
var adjectives = [
  "neon",
  "midnight",
  "electric",
  "golden",
  "silver",
  "crystal",
  "velvet",
  "static",
  "hollow",
  "distant",
  "bright",
  "blurred",
  "wild",
  "quiet",
  "loud",
  "tender",
  "broken",
  "unspoken",
  "secret",
  "reckless",
  "restless",
  "glowing",
  "fading",
  "burning",
  "frozen",
  "sunlit",
  "moonlit",
  "stormy",
  "rainy",
  "endless",
  "timeless",
  "paper",
  "plastic",
  "digital",
  "analog",
  "city",
  "coastal",
  "northern",
  "southern",
  "lunar",
  "solar",
  "magnetic",
  "gravity",
  "cosmic",
  "stellar",
  "chromatic",
  "sapphire",
  "amber",
  "azure",
  "violet",
  "scarlet",
  "obsidian",
  "opal",
  "ruby",
  "emerald",
  "porcelain",
  "carbon",
  "steel",
  "soft",
  "hard",
  "heavy",
  "weightless",
  "future",
  "retro",
  "glitch",
  "perfect",
  "imperfect",
  "fearless",
  "careless",
  "patient",
  "urgent",
  "hidden",
  "open",
  "private",
  "public",
  "parallel",
  "spiral",
  "silent",
  "shattered",
  "wired",
  "wireless",
  "radio",
  "pixel",
  "liquid",
  "solid",
  "electric-blue",
  "rose",
  "blackout",
  "afterglow",
  "high-speed",
  "low-fi",
  "hi-fi",
  "first",
  "last",
  "next",
  "final",
  "rare",
  "common",
  "strange",
  "familiar",
  "haunted",
  "blessed",
  "fragile",
  "iron",
  "paper-thin",
  "deep",
  "shallow",
  "slow",
  "fast",
  "hazy",
  "sharp",
  "warm",
  "cold",
  "unreal",
  "real",
  "new",
  "old",
  "ancient",
  "modern",
  "electric-pink",
  "ultraviolet",
  "infrared",
  "blue",
  "red",
  "white",
  "black",
  "grey",
  "midnight-blue",
  "sunset",
  "dawn",
  "twilight",
  "after-midnight",
  "before-dawn",
  "late-night",
  "early-morning",
  "covert",
  "overt",
  "glimmering",
  "flashing",
  "drifting",
  "steady",
  "wavering",
  "electric-summer",
  "winter",
  "spring",
  "autumn",
  "summer",
  "narrow",
  "wide",
  "open-ended",
  "closed-loop",
  "radiant",
  "dim",
  "synth",
  "bass",
  "brightline",
  "darkwave",
  "dream",
  "night",
  "day",
  "soft-focus",
  "hard-edge",
  "glass",
  "neon-lit",
  "street",
  "ocean",
  "sky",
  "underground",
  "overground",
  "topline",
  "bottomline",
  "heartbeat",
  "heartbeat-fast",
  "heartbeat-slow",
  "electric-heart",
  "paper-heart",
  "silk",
  "velour",
  "chrome",
  "titanium",
  "luminous",
  "shadow",
  "sudden",
  "gentle",
  "blue-hour",
  "gold-hour"
];
var nouns = [
  "city",
  "night",
  "dream",
  "static",
  "signal",
  "pulse",
  "echo",
  "shadow",
  "light",
  "glow",
  "storm",
  "rain",
  "thunder",
  "sky",
  "ocean",
  "river",
  "street",
  "avenue",
  "highway",
  "room",
  "mirror",
  "window",
  "door",
  "key",
  "lock",
  "heart",
  "voice",
  "silence",
  "noise",
  "fire",
  "ice",
  "ember",
  "spark",
  "star",
  "moon",
  "sun",
  "orbit",
  "gravity",
  "comet",
  "neon",
  "circuit",
  "wire",
  "frequency",
  "wave",
  "bassline",
  "melody",
  "hook",
  "chorus",
  "verse",
  "break",
  "drop",
  "build",
  "nightfall",
  "afterglow",
  "midnight",
  "dawn",
  "twilight",
  "rush",
  "kiss",
  "lie",
  "truth",
  "promise",
  "secret",
  "memory",
  "moment",
  "map",
  "road",
  "corner",
  "edge",
  "distance",
  "horizon",
  "orbit",
  "arcade",
  "station",
  "platform",
  "taxi",
  "train",
  "radio",
  "camera",
  "snapshot",
  "polaroid",
  "page",
  "letter",
  "postcard",
  "headline",
  "story",
  "chapter",
  "refrain",
  "heartbeat",
  "breath",
  "sigh",
  "glimmer",
  "shadowline",
  "sunrise",
  "sunset",
  "blueprint",
  "pattern",
  "signal",
  "noise-floor",
  "synthline",
  "kick",
  "snare",
  "hi-hat",
  "groove",
  "tempo",
  "chord",
  "minor-key",
  "major-key",
  "hotel",
  "rooftop",
  "basement",
  "alley",
  "bridge",
  "tunnel",
  "neighborhood",
  "district",
  "coast",
  "harbor",
  "lighthouse",
  "air",
  "dust",
  "smoke",
  "glass",
  "chrome",
  "velvet",
  "silk",
  "paper",
  "plastic",
  "pixel",
  "glitch",
  "drift",
  "loop",
  "strobe",
  "laser",
  "fog",
  "haze",
  "sparkle",
  "gravity",
  "constellation",
  "satellite",
  "nightdrive",
  "handshake",
  "goodbye",
  "hello",
  "afterparty",
  "hangover",
  "blue-hour",
  "gold-hour"
];
var verbs = [
  "chase",
  "follow",
  "forget",
  "remember",
  "hold",
  "leave",
  "find",
  "lose",
  "burn",
  "freeze",
  "drift",
  "run",
  "hide",
  "show",
  "turn",
  "fade",
  "glow",
  "fall",
  "rise",
  "wait",
  "breathe",
  "call",
  "answer",
  "promise",
  "break",
  "build",
  "dance",
  "move",
  "stay",
  "go"
];
var places = [
  "on the rooftop",
  "in the hallway",
  "by the river",
  "under streetlights",
  "in the backseat",
  "at the station",
  "in the club",
  "on the coastline",
  "beneath the neon",
  "under the moon",
  "in the quiet room",
  "inside the static",
  "between the lines",
  "in the dark",
  "in the blue hour"
];
var feelings = [
  "like home",
  "for the first time",
  "like we never left",
  "until the morning",
  "without a warning",
  "in perfect sync",
  "on repeat",
  "in slow motion",
  "in the afterglow",
  "in the silence",
  "in the noise",
  "under my skin"
];
function generateTitleCandidates(count) {
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 30) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const n2 = pick(nouns);
    const v = pick(verbs);
    const place = pick(places);
    const feel = pick(feelings);
    const pattern = attempts % 12;
    const text = pattern === 0 ? `When the ${a} ${n} calls` : pattern === 1 ? `${a} ${n}` : pattern === 2 ? `Echoes of the ${a} ${n}` : pattern === 3 ? `After the ${a} ${n}` : pattern === 4 ? `Under the ${a} ${n}` : pattern === 5 ? `Between ${a} ${n} and ${n2}` : pattern === 6 ? `This is how it feels ${feel}` : pattern === 7 ? `I ${v} ${place}` : pattern === 8 ? `We ${v} through the ${a} ${n}` : pattern === 9 ? `Don't let the ${a} ${n} fade` : pattern === 10 ? `I ${v} and you stay ${feel}` : `Under streetlights, we ${v} again`;
    const norm = normalize3(text);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push(text);
  }
  return out;
}
function generateAlbumCandidates(count) {
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 30) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const n2 = pick(nouns);
    const pattern = attempts % 6;
    const text = pattern === 0 ? `Stories from the ${a} ${n}` : pattern === 1 ? `Letters in the ${a} ${n}` : pattern === 2 ? `The ${a} ${n} Collection` : pattern === 3 ? `${a} ${n} and ${n2}` : pattern === 4 ? `Inside the ${a} ${n}` : `Between ${a} ${n} and ${n2}`;
    const norm = normalize3(text);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push(text);
  }
  return out;
}
function generateOpeningPairs(count) {
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 40) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const v = pick(verbs);
    const place = pick(places);
    const who = pick([
      "I",
      "We",
      "You",
      "Tonight",
      "Somewhere",
      "In my head",
      "In your eyes",
      "Under the neon",
      "After midnight"
    ]);
    const mood = pick([
      "love",
      "heartbreak",
      "longing",
      "regret",
      "hope",
      "jealousy",
      "desire",
      "nostalgia",
      "loneliness",
      "euphoria"
    ]);
    const time = pick([
      "tonight",
      "right now",
      "in the morning",
      "after midnight",
      "before dawn",
      "all summer",
      "all winter",
      "for one more hour"
    ]);
    const line1 = who === "I" || who === "We" || who === "You" ? `${who} ${v} the ${a} ${n} ${place}.` : `${who}, the ${a} ${n} feels too close ${time}.`;
    const line2 = pick([
      `My ${mood} is louder than the kick drum ${time}.`,
      `Your voice turns into static, and I still hear it ${time}.`,
      `I taste the goodbye in the air, sweet and cruel ${time}.`,
      `We promised we'd be fearless, then we blinked ${time}.`,
      `I keep the truth on mute, but it leaks through ${time}.`,
      `Hold me like a secret you can't keep ${time}.`,
      `If this is love, why does it hurt so clean ${time}?`,
      `I miss the version of us that never breaks ${time}.`,
      `Tell me it's real, even if it's only for the chorus ${time}.`,
      `I let the night decide who we are ${time}.`
    ]);
    const norm = normalize3(`${line1} ${line2}`);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push({ line1, line2 });
  }
  return out;
}

// electron/db/phrasePools.ts
function normalize4(text) {
  return String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
}
async function connect(cfg) {
  const client = new pg.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function poolStats(cfg) {
  const client = await connect(cfg);
  try {
    const openings = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from opening_pairs"
    );
    const titles = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from title_pool"
    );
    const albums = await client.query(
      "select count(1)::int as total, count(1) filter (where used_count = 0)::int as unused from album_pool"
    );
    return {
      openings: openings.rows[0],
      titles: titles.rows[0],
      albums: albums.rows[0]
    };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function importTitles(cfg, titles) {
  const rows = titles.map((t) => String(t || "").trim()).filter(Boolean).map((t) => ({ title: t, norm: normalize4(t) })).filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };
  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1e3;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk2 = rows.slice(i, i + chunkSize);
      const values = [];
      const params = [];
      let p = 1;
      for (const r of chunk2) {
        values.push(`($${p++}, $${p++})`);
        params.push(r.title, r.norm);
      }
      const q = `insert into title_pool(title, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function importAlbums(cfg, albums) {
  const rows = albums.map((t) => String(t || "").trim()).filter(Boolean).map((t) => ({ album: t, norm: normalize4(t) })).filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };
  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1e3;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk2 = rows.slice(i, i + chunkSize);
      const values = [];
      const params = [];
      let p = 1;
      for (const r of chunk2) {
        values.push(`($${p++}, $${p++})`);
        params.push(r.album, r.norm);
      }
      const q = `insert into album_pool(album, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function importOpenings(cfg, pairs) {
  const rows = pairs.map((p) => ({ line1: String(p.line1 || "").trim(), line2: String(p.line2 || "").trim() })).filter((x) => x.line1 && x.line2).map((x) => ({ ...x, norm: normalize4(`${x.line1} ${x.line2}`) })).filter((x) => x.norm);
  if (!rows.length) return { inserted: 0 };
  const client = await connect(cfg);
  try {
    await client.query("begin");
    let inserted = 0;
    const chunkSize = 1e3;
    for (let i = 0; i < rows.length; i += chunkSize) {
      const chunk2 = rows.slice(i, i + chunkSize);
      const values = [];
      const params = [];
      let p = 1;
      for (const r of chunk2) {
        values.push(`($${p++}, $${p++}, $${p++})`);
        params.push(r.line1, r.line2, r.norm);
      }
      const q = `insert into opening_pairs(line1, line2, norm) values ${values.join(",")} on conflict (norm) do nothing`;
      const res = await client.query(q, params);
      inserted += res.rowCount ?? 0;
    }
    await client.query("commit");
    return { inserted };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function pickBatchAndMark(cfg, opts) {
  const n = Math.max(1, Math.min(200, Math.floor(opts.n)));
  const client = await connect(cfg);
  const maxAttempts = 6;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      await client.query("begin");
      const out = { openings: [], titles: [], albums: [] };
      if (opts.opening) {
        const r = await client.query(
          "select id, line1, line2 from opening_pairs order by used_count asc, random() limit $1 for update skip locked",
          [n]
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update opening_pairs set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.openings = r.rows.map((x) => ({ id: Number(x.id), line1: String(x.line1), line2: String(x.line2) }));
        }
      }
      if (opts.title) {
        const r = await client.query(
          "select id, title from title_pool order by used_count asc, random() limit $1 for update skip locked",
          [n]
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update title_pool set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.titles = r.rows.map((x) => ({ id: Number(x.id), title: String(x.title) }));
        }
      }
      if (opts.album) {
        const r = await client.query(
          "select id, album from album_pool order by used_count asc, random() limit $1 for update skip locked",
          [n]
        );
        const ids = r.rows.map((x) => Number(x.id));
        if (ids.length) {
          await client.query("update album_pool set used_count = used_count + 1, used_at = now() where id = any($1)", [ids]);
          out.albums = r.rows.map((x) => ({ id: Number(x.id), album: String(x.album) }));
        }
      }
      await client.query("commit");
      return out;
    } catch (e) {
      await client.query("rollback").catch(() => void 0);
      const code = e && typeof e === "object" ? e.code : void 0;
      const msg = e instanceof Error ? e.message : String(e);
      const isDeadlock = code === "40P01" || /deadlock detected/i.test(msg);
      if (!isDeadlock || attempt === maxAttempts - 1) throw e;
      await new Promise((r) => setTimeout(r, 50 * (attempt + 1)));
      continue;
    }
  }
  await client.end().catch(() => void 0);
  throw new Error("Failed to pick batch (retry exhausted)");
}
async function listPool(cfg, input) {
  const limit = Math.max(1, Math.min(500, Math.floor(input.limit)));
  const offset = Math.max(0, Math.floor(input.offset));
  const client = await connect(cfg);
  try {
    if (input.kind === "titles") {
      const r2 = await client.query(
        'select id, title as text, used_count as "usedCount", created_at as "createdAt" from title_pool order by id desc limit $1 offset $2',
        [limit, offset]
      );
      return { kind: "titles", rows: r2.rows.map((x) => ({ id: Number(x.id), text: String(x.text), usedCount: Number(x.usedCount), createdAt: String(x.createdAt) })) };
    }
    if (input.kind === "albums") {
      const r2 = await client.query(
        'select id, album as text, used_count as "usedCount", created_at as "createdAt" from album_pool order by id desc limit $1 offset $2',
        [limit, offset]
      );
      return { kind: "albums", rows: r2.rows.map((x) => ({ id: Number(x.id), text: String(x.text), usedCount: Number(x.usedCount), createdAt: String(x.createdAt) })) };
    }
    const r = await client.query(
      'select id, line1, line2, used_count as "usedCount", created_at as "createdAt" from opening_pairs order by id desc limit $1 offset $2',
      [limit, offset]
    );
    return {
      kind: "openings",
      rows: r.rows.map((x) => ({
        id: Number(x.id),
        line1: String(x.line1),
        line2: String(x.line2),
        usedCount: Number(x.usedCount),
        createdAt: String(x.createdAt)
      }))
    };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function generateAndInsert(cfg, input) {
  const target = Math.max(1, Math.min(2e5, Math.floor(input.count)));
  let inserted = 0;
  let rounds = 0;
  while (inserted < target && rounds < 40) {
    rounds += 1;
    const remaining = target - inserted;
    const batch = Math.min(5e3, remaining);
    if (input.kind === "titles") {
      const candidates = generateTitleCandidates(batch * 2);
      const r = await importTitles(cfg, candidates);
      inserted += r.inserted;
    } else if (input.kind === "albums") {
      const candidates = generateAlbumCandidates(batch * 2);
      const r = await importAlbums(cfg, candidates);
      inserted += r.inserted;
    } else {
      const candidates = generateOpeningPairs(batch * 2);
      const r = await importOpenings(cfg, candidates);
      inserted += r.inserted;
    }
    if (rounds >= 6 && inserted === 0) break;
  }
  return { inserted };
}
async function clearPool(cfg, kind) {
  const client = await connect(cfg);
  try {
    await client.query("begin");
    await client.query("set local lock_timeout = '3s'");
    await client.query("set local statement_timeout = '20s'");
    if (kind === "titles") await client.query("truncate table title_pool restart identity");
    else if (kind === "albums") await client.query("truncate table album_pool restart identity");
    else await client.query("truncate table opening_pairs restart identity");
    await client.query("commit");
    return { ok: true };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    return { ok: false, message: e instanceof Error ? e.message : "Failed to clear" };
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/db/songStore.ts
import * as pg2 from "pg";
async function connect2(cfg) {
  const client = new pg2.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function upsertSong(cfg, input) {
  const client = await connect2(cfg);
  try {
    await client.query(
      `insert into songs(
        song_uid, title, album,
        lyrics_raw, lyrics_polished,
        song_description, song_structure,
        language, creativity, batch_id, batch_index,
        status, created_at
      ) values (
        $1,$2,$3,
        $4,$5,
        $6,$7,
        $8,$9,$10,$11,
        $12, coalesce($13::timestamp, now())
      )
      on conflict (song_uid) do update set
        title = excluded.title,
        album = excluded.album,
        lyrics_raw = excluded.lyrics_raw,
        lyrics_polished = excluded.lyrics_polished,
        song_description = excluded.song_description,
        song_structure = excluded.song_structure,
        language = excluded.language,
        creativity = excluded.creativity,
        batch_id = excluded.batch_id,
        batch_index = excluded.batch_index,
        status = excluded.status`,
      [
        input.songUid,
        input.title,
        input.album,
        input.lyricsRaw,
        input.lyricsPolished,
        input.songDescription,
        input.songStructure,
        input.language,
        input.creativity,
        input.batchId ?? null,
        typeof input.batchIndex === "number" && Number.isFinite(input.batchIndex) ? Math.floor(input.batchIndex) : null,
        input.status ?? "generated",
        input.createdAtIso ?? null
      ]
    );
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function insertHistory(cfg, input) {
  const client = await connect2(cfg);
  try {
    await client.query("insert into history(kind, song_uid, message) values ($1, $2, $3)", [
      input.kind,
      input.songUid ?? null,
      input.message
    ]);
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function getRecentForUniqueness(cfg, n) {
  const limit = Math.max(1, Math.min(5e3, Math.floor(n)));
  const client = await connect2(cfg);
  try {
    const r = await client.query(
      "select title, album, lyrics_raw, lyrics_polished from songs order by created_at desc limit $1",
      [limit]
    );
    return r.rows.map((x) => ({
      title: String(x.title ?? ""),
      album: String(x.album ?? ""),
      lyricsRaw: String(x.lyrics_raw ?? ""),
      lyricsPolished: String(x.lyrics_polished ?? "")
    }));
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function listSongsByBatchId(cfg, batchId) {
  const client = await connect2(cfg);
  try {
    const res = await client.query(
      "select song_uid, title, album, lyrics_raw, lyrics_polished, song_description, song_structure, language, creativity, batch_id, batch_index, created_at from songs where batch_id = $1 order by created_at asc",
      [batchId]
    );
    return res.rows.map((r) => ({
      id: String(r.song_uid),
      title: String(r.title ?? ""),
      album: String(r.album ?? ""),
      lyricsRaw: String(r.lyrics_raw ?? ""),
      lyricsPolished: String(r.lyrics_polished ?? ""),
      songDescription: String(r.song_description ?? ""),
      songStructure: String(r.song_structure ?? ""),
      language: String(r.language ?? "English"),
      creativity: Number(r.creativity ?? 50),
      batchId: String(r.batch_id ?? ""),
      batchIndex: typeof r.batch_index === "number" ? Number(r.batch_index) : r.batch_index ? Number(r.batch_index) : void 0,
      createdAt: new Date(r.created_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function clearGenerated(cfg) {
  const client = await connect2(cfg);
  try {
    await client.query("begin");
    await client.query("set local lock_timeout = '3s'");
    await client.query("set local statement_timeout = '20s'");
    await client.query("truncate table history restart identity");
    await client.query("truncate table songs restart identity");
    await client.query("commit");
    return { ok: true };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    return { ok: false, message: e instanceof Error ? e.message : "Failed to clear" };
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/suno/sunoApi.ts
import path3 from "node:path";
import { promises as fs3 } from "node:fs";
import { createHash } from "node:crypto";
function hashSunoGenerateRequest(input) {
  const normalized = {
    model: String(input.model || "").trim(),
    title: String(input.title || "").trim(),
    prompt: String(input.prompt || "").trim(),
    style: String(input.style || "").trim(),
    instrumental: Boolean(input.instrumental)
  };
  return createHash("sha256").update(JSON.stringify(normalized)).digest("hex");
}
function sanitizeFileName(input) {
  return String(input || "").replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim().slice(0, 120);
}
async function httpJson(url, init) {
  const resp = await fetch(url, init);
  const raw = await resp.text();
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const j = JSON.parse(raw);
      if (j && typeof j === "object") {
        const rec = j;
        const topMsg = typeof rec.message === "string" ? rec.message : null;
        const err = rec.error && typeof rec.error === "object" ? rec.error : null;
        const errMsg = err && typeof err.message === "string" ? err.message : null;
        msg = topMsg || errMsg || msg;
      }
    } catch {
      if (raw.trim()) msg = raw.slice(0, 280);
    }
    throw new Error(msg);
  }
  return JSON.parse(raw);
}
function assertApiOk(resp) {
  if (typeof resp.code === "number" && resp.code !== 200) {
    const msg = String(resp.msg || "Suno API request failed").trim();
    throw new Error(`Suno API error ${resp.code}: ${msg}`);
  }
}
function asClips(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((x) => x && typeof x === "object").map((x) => x).map((r) => ({
    audioUrl: typeof r.audioUrl === "string" ? r.audioUrl : void 0,
    audio_url: typeof r.audio_url === "string" ? r.audio_url : void 0,
    id: typeof r.id === "string" ? r.id : void 0,
    title: typeof r.title === "string" ? r.title : void 0
  }));
}
function pickFirstArray(root) {
  if (!root || typeof root !== "object") return null;
  const r = root;
  if (Array.isArray(r.data)) return r.data;
  if (Array.isArray(r.sunoData)) return r.sunoData;
  if (r.response && typeof r.response === "object") {
    const rr = r.response;
    if (Array.isArray(rr.data)) return rr.data;
    if (Array.isArray(rr.sunoData)) return rr.sunoData;
  }
  return null;
}
async function sunoApiGenerate(input) {
  const body = {
    customMode: true,
    instrumental: Boolean(input.instrumental),
    model: input.model,
    title: input.title,
    prompt: input.lyrics,
    style: input.style,
    callBackUrl: String(input.callbackUrl || "https://api.example.com/callback").trim()
  };
  const res = await httpJson("https://api.sunoapi.org/api/v1/generate", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${input.apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  assertApiOk(res);
  const taskId = String(res.data?.taskId || res.data?.task_id || res.taskId || res.task_id || "").trim();
  if (!taskId) {
    const safe = JSON.stringify({ code: res.code, msg: res.msg, data: res.data ?? null }).slice(0, 500);
    throw new Error(`Suno API did not return taskId. Response: ${safe}`);
  }
  return { taskId };
}
async function sunoApiGetRecordInfo(apiKey, taskId) {
  const url = new URL("https://api.sunoapi.org/api/v1/generate/record-info");
  url.searchParams.set("taskId", taskId);
  const res = await httpJson(url.toString(), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${apiKey}`
    }
  });
  assertApiOk(res);
  const status = String(res.data?.status || res.status || "PENDING");
  const nested = pickFirstArray(res.data);
  const d = res.data;
  const respObj = d && typeof d.response === "object" ? d.response : null;
  const clips = asClips(
    (d ? d.clips : void 0) ?? (d ? d.songs : void 0) ?? (d ? d.sunoData : void 0) ?? (respObj ? respObj.clips : void 0) ?? (respObj ? respObj.songs : void 0) ?? (respObj ? respObj.sunoData : void 0) ?? nested ?? res.clips ?? res.songs
  );
  return { status, clips, raw: res };
}
async function sunoApiTryGetTracks(apiKey, taskId) {
  const info = await sunoApiGetRecordInfo(apiKey, taskId);
  const urls = info.clips.map((c) => String(c.audioUrl || c.audio_url || "").trim()).filter(Boolean);
  return { status: info.status, audioUrls: urls.slice(0, 2), info };
}
async function downloadToFile(url, outPath) {
  await fs3.mkdir(path3.dirname(outPath), { recursive: true });
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Download failed (${resp.status})`);
  const buf = Buffer.from(await resp.arrayBuffer());
  await fs3.writeFile(outPath, buf);
  return outPath;
}
function buildSunoOutputPaths(opts) {
  const base = sanitizeFileName(opts.title);
  const prefix = Number.isFinite(opts.trackNo) ? `${Math.max(1, Math.floor(opts.trackNo ?? 1))}. ` : "";
  return {
    ok: path3.join(opts.outputDir, `${prefix}${base}_OK.mp3`),
    alt: path3.join(opts.outputDir, `${prefix}${base}_Alt.mp3`)
  };
}

// electron/db/sunoTaskStore.ts
import * as pg3 from "pg";
async function connect3(cfg) {
  const client = new pg3.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function getSunoTaskByRequestHash(cfg, requestHash) {
  const client = await connect3(cfg);
  try {
    const res = await client.query(
      "select request_hash, song_uid, batch_id, track_no, model, title, style, instrumental, task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir from suno_tasks where request_hash = $1",
      [requestHash]
    );
    const row = res.rows[0];
    if (!row) return null;
    return {
      requestHash: String(row.request_hash),
      songUid: String(row.song_uid || ""),
      batchId: String(row.batch_id || ""),
      trackNo: row.track_no === null || row.track_no === void 0 ? null : Number(row.track_no),
      model: String(row.model || ""),
      title: String(row.title || ""),
      style: String(row.style || ""),
      instrumental: Boolean(row.instrumental),
      taskId: String(row.task_id || ""),
      status: String(row.status || ""),
      audioUrlOk: row.audio_url_ok ? String(row.audio_url_ok) : null,
      audioUrlAlt: row.audio_url_alt ? String(row.audio_url_alt) : null,
      outputDirOk: row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null,
      outputDirAlt: row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null
    };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function getLatestSunoOutputDirsBySongUid(cfg, songUid) {
  const client = await connect3(cfg);
  try {
    const res = await client.query(
      "select output_dir_ok, output_dir_alt, output_dir from suno_tasks where song_uid = $1 order by updated_at desc, id desc limit 1",
      [songUid]
    );
    const row = res.rows[0];
    if (!row) return { okDir: null, altDir: null };
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function getLatestSunoOutputDirsByBatchId(cfg, batchId) {
  const key = String(batchId || "").trim();
  if (!key) return { ok: false, message: "Batch ID is empty" };
  const client = await connect3(cfg);
  try {
    const res = await client.query(
      "select output_dir_ok, output_dir_alt, output_dir from suno_tasks where batch_id = $1 order by updated_at desc, id desc limit 1",
      [key]
    );
    const row = res.rows[0];
    if (!row) return { ok: false, message: "No Suno output directories found for batch" };
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { ok: true, okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function getLatestSunoBatchWithOutputDirs(cfg) {
  const client = await connect3(cfg);
  try {
    const res = await client.query(
      "select batch_id, output_dir_ok, output_dir_alt, output_dir from suno_tasks where coalesce(output_dir_ok, output_dir) is not null order by updated_at desc, id desc limit 1"
    );
    const row = res.rows[0];
    if (!row) return { ok: false, message: "No batches found" };
    const batchId = String(row.batch_id || "").trim();
    const okDir = row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null;
    const altDir = row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null;
    return { ok: true, batchId, okDir: okDir ? okDir.trim() : null, altDir: altDir ? altDir.trim() : null };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function upsertSunoTask(cfg, input) {
  const client = await connect3(cfg);
  try {
    await client.query(
      `insert into suno_tasks(
        request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
        task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir, updated_at
      ) values (
        $1,$2,$3,$4,$5,$6,$7,$8,
        $9,$10,$11,$12,$13,$14,$15, now()
      )
      on conflict (request_hash) do update set
        song_uid = excluded.song_uid,
        batch_id = excluded.batch_id,
        track_no = coalesce(excluded.track_no, suno_tasks.track_no),
        model = excluded.model,
        title = excluded.title,
        style = excluded.style,
        instrumental = excluded.instrumental,
        task_id = excluded.task_id,
        status = excluded.status,
        audio_url_ok = coalesce(excluded.audio_url_ok, suno_tasks.audio_url_ok),
        audio_url_alt = coalesce(excluded.audio_url_alt, suno_tasks.audio_url_alt),
        output_dir_ok = coalesce(excluded.output_dir_ok, suno_tasks.output_dir_ok),
        output_dir_alt = coalesce(excluded.output_dir_alt, suno_tasks.output_dir_alt),
        output_dir = coalesce(excluded.output_dir, suno_tasks.output_dir),
        updated_at = now()`,
      [
        input.requestHash,
        input.songUid,
        input.batchId,
        typeof input.trackNo === "number" && Number.isFinite(input.trackNo) ? Math.floor(input.trackNo) : null,
        input.model,
        input.title,
        input.style,
        input.instrumental,
        input.taskId,
        input.status,
        input.audioUrlOk ?? null,
        input.audioUrlAlt ?? null,
        input.outputDirOk ?? null,
        input.outputDirAlt ?? null,
        input.outputDir ?? null
      ]
    );
    return { ok: true };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function listPendingSunoTasks(cfg, limit) {
  const client = await connect3(cfg);
  try {
    const res = await client.query(
      `select request_hash, song_uid, batch_id, track_no, model, title, style, instrumental, task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir
       from suno_tasks
       where task_id is not null
         and task_id <> ''
         and (audio_url_ok is null or audio_url_alt is null)
         and coalesce(status, '') not in ('CREATE_TASK_FAILED','GENERATE_AUDIO_FAILED')
       order by updated_at desc, id desc
       limit $1`,
      [Math.max(1, Math.min(200, limit))]
    );
    return res.rows.map((row) => ({
      requestHash: String(row.request_hash),
      songUid: String(row.song_uid || ""),
      batchId: String(row.batch_id || ""),
      trackNo: row.track_no === null || row.track_no === void 0 ? null : Number(row.track_no),
      model: String(row.model || ""),
      title: String(row.title || ""),
      style: String(row.style || ""),
      instrumental: Boolean(row.instrumental),
      taskId: String(row.task_id || ""),
      status: String(row.status || ""),
      audioUrlOk: row.audio_url_ok ? String(row.audio_url_ok) : null,
      audioUrlAlt: row.audio_url_alt ? String(row.audio_url_alt) : null,
      outputDirOk: row.output_dir_ok ? String(row.output_dir_ok) : row.output_dir ? String(row.output_dir) : null,
      outputDirAlt: row.output_dir_alt ? String(row.output_dir_alt) : row.output_dir ? String(row.output_dir) : null
    }));
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/suno/sunoSubmitter.ts
import { existsSync } from "node:fs";
var SunoSubmitter = class {
  constructor(opts) {
    this.opts = opts;
  }
  queue = [];
  running = 0;
  batchIndexCache = /* @__PURE__ */ new Map();
  enqueue(item) {
    this.queue.push(item);
    this.pump();
  }
  pump() {
    while (this.running < this.opts.maxConcurrent && this.queue.length) {
      const item = this.queue.shift();
      if (!item) return;
      this.running += 1;
      void this.runOne(item).catch(() => void 0).finally(() => {
        this.running -= 1;
        this.pump();
      });
    }
  }
  async trackNoForSong(db, song) {
    const batchId = String(song.batchId ?? "").trim();
    if (!batchId) return void 0;
    const songUid = String(song.id || "").trim();
    if (!songUid) return void 0;
    let idx = this.batchIndexCache.get(batchId);
    if (!idx) {
      const songs = await listSongsByBatchId(db, batchId);
      idx = new Map(songs.map((s, i) => [s.id, i + 1]));
      this.batchIndexCache.set(batchId, idx);
    }
    return idx.get(songUid);
  }
  emit(e) {
    this.opts.onEvent?.(e);
  }
  async runOne(item) {
    const apiKey = String(item.apiKey || "").trim();
    if (!apiKey) {
      this.emit({ jobId: item.jobId, status: "failed", message: "Suno auto-submit skipped: missing API key" });
      return;
    }
    const callbackUrl = String(item.callbackUrl || "").trim() || "https://api.example.com/callback";
    const prompt = item.song.lyricsPolished || item.song.lyricsRaw;
    const requestHash = hashSunoGenerateRequest({
      model: item.model,
      title: item.song.title,
      prompt,
      style: item.song.songDescription,
      instrumental: false
    });
    this.emit({ jobId: item.jobId, status: "running", message: `Suno: submitting (${item.song.title})` });
    const cached = await getSunoTaskByRequestHash(item.db, requestHash);
    const outputDirOk = String(item.outputDirOk || "").trim();
    const outputDirAlt = String(item.outputDirAlt || "").trim() || outputDirOk;
    const trackNo = typeof item.song.batchIndex === "number" && Number.isFinite(item.song.batchIndex) ? Math.floor(item.song.batchIndex) : await this.trackNoForSong(item.db, item.song);
    if (cached?.audioUrlOk && cached.audioUrlAlt) {
      const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: item.song.title, trackNo });
      const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: item.song.title, trackNo });
      if (!existsSync(pathsOk.ok)) await downloadToFile(cached.audioUrlOk, pathsOk.ok);
      if (!existsSync(pathsAlt.alt)) await downloadToFile(cached.audioUrlAlt, pathsAlt.alt);
      this.emit({ jobId: item.jobId, status: "completed", message: `Suno: downloaded cached (${item.song.title})` });
      return;
    }
    let taskId = String(cached?.taskId || "").trim();
    if (!taskId) {
      const gen = await sunoApiGenerate({
        apiKey,
        model: item.model,
        title: item.song.title,
        lyrics: prompt,
        style: item.song.songDescription,
        instrumental: false,
        callbackUrl
      });
      taskId = gen.taskId;
    }
    await upsertSunoTask(item.db, {
      requestHash,
      songUid: item.song.id,
      batchId: item.song.batchId ?? "",
      trackNo,
      model: item.model,
      title: item.song.title,
      style: item.song.songDescription,
      instrumental: false,
      taskId,
      status: "PENDING",
      outputDirOk,
      outputDirAlt
    });
    const r = await sunoApiTryGetTracks(apiKey, taskId);
    if (r.audioUrls.length >= 2) {
      const okUrl = String(r.audioUrls[0] || "").trim();
      const altUrl = String(r.audioUrls[1] || "").trim();
      await upsertSunoTask(item.db, {
        requestHash,
        songUid: item.song.id,
        batchId: item.song.batchId ?? "",
        trackNo,
        model: item.model,
        title: item.song.title,
        style: item.song.songDescription,
        instrumental: false,
        taskId,
        status: String(r.status || "SUCCESS"),
        audioUrlOk: okUrl,
        audioUrlAlt: altUrl,
        outputDirOk,
        outputDirAlt
      });
      const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: item.song.title, trackNo });
      const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: item.song.title, trackNo });
      if (okUrl && !existsSync(pathsOk.ok)) await downloadToFile(okUrl, pathsOk.ok);
      if (altUrl && !existsSync(pathsAlt.alt)) await downloadToFile(altUrl, pathsAlt.alt);
      this.emit({ jobId: item.jobId, status: "completed", message: `Suno: downloaded (${item.song.title})` });
      return;
    }
    this.emit({ jobId: item.jobId, status: "completed", message: `Suno: submitted (${item.song.title})` });
  }
};

// electron/jobQueue.ts
var poolBuffers = /* @__PURE__ */ new Map();
var recentTitlePrefixesByDb = /* @__PURE__ */ new Map();
var batchAlbumByBatchId = /* @__PURE__ */ new Map();
var recentAvoidCache = /* @__PURE__ */ new Map();
function poolKey(db) {
  return `${db.user}@${db.host}:${db.port}/${db.database}`;
}
async function getPooled(db, opts) {
  const key = poolKey(db);
  const buf = poolBuffers.get(key) ?? { openings: [], titles: [], albums: [] };
  const needOpenings = opts.opening && buf.openings.length === 0;
  const needTitles = opts.title && buf.titles.length === 0;
  const needAlbums = opts.album && buf.albums.length === 0;
  if (needOpenings || needTitles || needAlbums) {
    const batch = await pickBatchAndMark(db, { opening: needOpenings, title: needTitles, album: needAlbums, n: 40 });
    if (batch.openings.length) buf.openings.push(...batch.openings.map((o) => ({ line1: o.line1, line2: o.line2 })));
    if (batch.titles.length) buf.titles.push(...batch.titles.map((t) => t.title));
    if (batch.albums.length) buf.albums.push(...batch.albums.map((a) => a.album));
    poolBuffers.set(key, buf);
  }
  return {
    opening: opts.opening ? buf.openings.shift() : void 0,
    title: opts.title ? pickNextTitle(key, buf) : void 0,
    album: opts.album ? buf.albums.shift() : void 0
  };
}
function cleanupBatchAlbums() {
  const cutoff = Date.now() - 6 * 60 * 60 * 1e3;
  for (const [k, v] of batchAlbumByBatchId) {
    if (v.createdAtMs < cutoff) batchAlbumByBatchId.delete(k);
  }
}
function normalize5(s) {
  return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
}
function firstWord(text) {
  const t = normalize5(text);
  if (!t) return "";
  return t.split(" ")[0] ?? "";
}
function pickNextTitle(dbKey, buf) {
  if (!buf.titles.length) return void 0;
  const recent = recentTitlePrefixesByDb.get(dbKey) ?? [];
  const avoid = new Set(recent);
  const preferNot = /* @__PURE__ */ new Set(["i", "we", "don't", "dont"]);
  function takeAt(idx) {
    const [picked] = buf.titles.splice(idx, 1);
    const prefix = firstWord(picked);
    if (prefix) {
      const next = [...recent, prefix].slice(-3);
      recentTitlePrefixesByDb.set(dbKey, next);
    }
    return picked;
  }
  const idxPreferred = buf.titles.findIndex((t) => {
    const p = firstWord(t);
    return p && !avoid.has(p) && !preferNot.has(p);
  });
  if (idxPreferred >= 0) return takeAt(idxPreferred);
  const idxAvoidOnly = buf.titles.findIndex((t) => {
    const p = firstWord(t);
    return p && !avoid.has(p);
  });
  if (idxAvoidOnly >= 0) return takeAt(idxAvoidOnly);
  return takeAt(0);
}
function opening23(lyrics) {
  const lines = String(lyrics || "").split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 2);
  return lines.join("\n");
}
function cleanupAvoidCache() {
  const cutoff = Date.now() - 10 * 60 * 1e3;
  for (const [k, v] of recentAvoidCache) {
    if (v.createdAtMs < cutoff) recentAvoidCache.delete(k);
  }
}
async function getAvoidLists(db, historyWindow) {
  cleanupAvoidCache();
  const key = `${poolKey(db)}|h=${historyWindow}`;
  const cached = recentAvoidCache.get(key);
  if (cached) return cached;
  const recent = await getRecentForUniqueness(db, historyWindow);
  const titleSet = /* @__PURE__ */ new Set();
  const albumSet = /* @__PURE__ */ new Set();
  const openingSet = /* @__PURE__ */ new Set();
  for (const s of recent) {
    const t = normalize5(s.title);
    const a = normalize5(s.album);
    const o = normalize5(opening23(s.lyricsPolished || s.lyricsRaw));
    if (t) titleSet.add(t);
    if (a) albumSet.add(a);
    if (o) openingSet.add(o);
  }
  const titles = Array.from(titleSet).slice(0, 120);
  const albums = Array.from(albumSet).slice(0, 120);
  const openings = Array.from(openingSet).slice(0, 120);
  const out = { titles, albums, openings, createdAtMs: Date.now() };
  recentAvoidCache.set(key, out);
  return out;
}
function nowIso2() {
  return (/* @__PURE__ */ new Date()).toISOString();
}
function emitEvent(emitter, event) {
  emitter.emit("event", { ...event, createdAt: nowIso2() });
}
async function sleep(ms) {
  await new Promise((r) => setTimeout(r, ms));
}
var JobQueue = class {
  emitter = new EventEmitter();
  queue = [];
  running = false;
  current = null;
  sunoSubmitter = new SunoSubmitter({
    maxConcurrent: 5,
    onEvent: (e) => emitEvent(this.emitter, {
      jobId: e.jobId,
      jobType: "suno",
      status: e.status,
      message: e.message,
      progress: e.progress
    })
  });
  onEvent(listener) {
    this.emitter.on("event", listener);
    return () => this.emitter.off("event", listener);
  }
  enqueue(payload) {
    const jobId = randomUUID2();
    const job = { jobId, payload, cancelled: false };
    this.queue.push(job);
    emitEvent(this.emitter, {
      jobId,
      jobType: payload.jobType,
      status: "queued",
      message: `${payload.jobType} queued`
    });
    void this.run();
    return { jobId };
  }
  cancel(jobId) {
    if (this.current?.jobId === jobId) {
      this.current.cancelled = true;
      emitEvent(this.emitter, {
        jobId,
        jobType: this.current.payload.jobType,
        status: "cancelled",
        message: "cancel requested"
      });
      return { ok: true };
    }
    const idx = this.queue.findIndex((x) => x.jobId === jobId);
    if (idx >= 0) {
      const [removed] = this.queue.splice(idx, 1);
      emitEvent(this.emitter, {
        jobId,
        jobType: removed.payload.jobType,
        status: "cancelled",
        message: "cancelled"
      });
      return { ok: true };
    }
    return { ok: false };
  }
  getState() {
    return {
      running: this.running,
      currentJobId: this.current?.jobId ?? null,
      queuedCount: this.queue.length
    };
  }
  async run() {
    if (this.running) return;
    this.running = true;
    try {
      while (this.queue.length) {
        const job = this.queue.shift();
        if (!job) break;
        this.current = job;
        await this.process(job);
        this.current = null;
      }
    } finally {
      this.running = false;
      this.current = null;
    }
  }
  async process(job) {
    const jobType = job.payload.jobType;
    const action = job.payload.jobType === "workflow" ? job.payload.action : void 0;
    const versionType = job.payload.jobType === "merge" ? job.payload.versionType : void 0;
    let song;
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType,
      status: "running",
      message: `${jobType} started`,
      progress: 0,
      action,
      versionType
    });
    try {
      if (jobType === "workflow") {
        const action2 = job.payload.jobType === "workflow" ? job.payload.action : "run";
        if (action2 === "generate") song = await this.runGenerate(job);
        else await this.runMockWorkflow(job);
      } else if (jobType === "merge") {
        await this.runMerge(job);
      } else {
        await this.runSuno(job);
      }
      if (job.cancelled) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType,
          status: "cancelled",
          message: "cancelled",
          action,
          versionType
        });
        return;
      }
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType,
        status: "completed",
        message: action ? `${action} completed` : `${jobType} completed`,
        progress: 100,
        action,
        versionType,
        song
      });
    } catch (e) {
      if (e instanceof Error) {
        console.error(`[jobQueue] job failed ${job.jobId} (${jobType})`, e.stack || e.message);
      } else {
        console.error(`[jobQueue] job failed ${job.jobId} (${jobType})`, e);
      }
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType,
        status: "failed",
        message: e instanceof Error ? e.message : "job failed",
        action,
        versionType
      });
    }
  }
  async runMockWorkflow(job) {
    const action = job.payload.jobType === "workflow" ? job.payload.action : "run";
    const steps = [
      { p: 10, m: `${action}: preparing` },
      { p: 35, m: `${action}: generating` },
      { p: 65, m: `${action}: processing` },
      { p: 90, m: `${action}: finalizing` }
    ];
    for (const s of steps) {
      if (job.cancelled) return;
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "workflow",
        status: "running",
        message: s.m,
        progress: s.p,
        action
      });
      await sleep(450);
    }
  }
  async runMerge(job) {
    if (job.payload.jobType !== "merge") return;
    const { versionType, chunkSize, inputDir, outputDir, ffmpegPath } = job.payload;
    if (!ffmpegPath || !ffmpegPath.trim()) throw new Error("FFmpeg path is not configured");
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `scanning ${inputDir}`,
      progress: 5,
      versionType
    });
    const result = await mergeAudioByVersion({
      ffmpegPath,
      inputDir,
      outputDir,
      versionType,
      chunkSize
    });
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `inputs OK=${result.inputCounts.OK} ALT=${result.inputCounts.ALT}`,
      progress: 25,
      versionType
    });
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "merge",
      status: "running",
      message: `created ${result.outputFiles.length} merged files`,
      progress: 90,
      versionType
    });
  }
  async runSuno(job) {
    if (job.payload.jobType !== "suno") return;
    const { batchId, expectedCount } = job.payload;
    let effectiveExpectedCount = expectedCount;
    const db = job.payload.db;
    if (!db) throw new Error("Postgres is not configured for Suno automation");
    const retryCount = Math.max(1, job.payload.sunoRetryCount ?? 3);
    const apiKey = String(job.payload.sunoApiKey || "").trim();
    if (!apiKey) throw new Error("Suno API key is not configured");
    let songs = (job.payload.songs ?? []).filter(Boolean);
    if (!songs.length) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `waiting for ${expectedCount} generated songs in batch ${batchId}`,
        progress: 5
      });
      const waitForSongsTimeoutMs = Math.max(15 * 6e4, expectedCount * 2 * 6e4);
      const start = Date.now();
      songs = await listSongsByBatchId(db, batchId);
      while (!job.cancelled && songs.length < expectedCount && Date.now() - start < waitForSongsTimeoutMs) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType: "suno",
          status: "running",
          message: `songs ready: ${songs.length}/${expectedCount}`,
          progress: Math.min(20, Math.floor(20 * songs.length / Math.max(1, expectedCount)))
        });
        await sleep(2e3);
        songs = await listSongsByBatchId(db, batchId);
      }
      if (job.cancelled) return;
      if (songs.length < expectedCount) {
        emitEvent(this.emitter, {
          jobId: job.jobId,
          jobType: "suno",
          status: "running",
          message: `Timed out waiting for songs: ${songs.length}/${expectedCount} (continuing with ${songs.length})`,
          progress: 20
        });
        effectiveExpectedCount = songs.length;
      }
    }
    const outputDirOk = String(job.payload.sunoOutputDirOk || job.payload.sunoOutputDir || job.payload.downloadsDir || "").trim();
    if (!outputDirOk) throw new Error("Suno output directory is not configured");
    const outputDirAlt = String(job.payload.sunoOutputDirAlt || outputDirOk).trim() || outputDirOk;
    const version = job.payload.version ?? "v5.5";
    const model = version === "v5" ? "V5" : "V5_5";
    const callbackUrl = String(job.payload.sunoCallbackUrl || "").trim() || "https://api.example.com/callback";
    let deferred = 0;
    const runSongs = songs.slice(0, effectiveExpectedCount);
    for (let i = 0; i < runSongs.length; i += 1) {
      if (job.cancelled) return;
      const song = runSongs[i];
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `Suno API: generating ${i + 1}/${runSongs.length} (${song.title})`,
        progress: 20 + Math.floor(60 * i / Math.max(1, runSongs.length))
      });
      let lastErr;
      for (let attempt = 0; attempt < retryCount; attempt += 1) {
        try {
          const prompt = song.lyricsPolished || song.lyricsRaw;
          const requestHash = hashSunoGenerateRequest({
            model,
            title: song.title,
            prompt,
            style: song.songDescription,
            instrumental: false
          });
          const cached = await getSunoTaskByRequestHash(db, requestHash);
          let taskId = cached?.taskId || "";
          if (cached?.audioUrlOk && cached.audioUrlAlt) {
            emitEvent(this.emitter, {
              jobId: job.jobId,
              jobType: "suno",
              status: "running",
              message: `Suno API: using cached result (${i + 1}/${runSongs.length})`,
              progress: 45 + Math.floor(30 * i / Math.max(1, runSongs.length))
            });
            const trackNo = typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : i + 1;
            const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: song.title, trackNo });
            const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: song.title, trackNo });
            await downloadToFile(cached.audioUrlOk, pathsOk.ok);
            await downloadToFile(cached.audioUrlAlt, pathsAlt.alt);
            break;
          }
          if (!taskId) {
            const gen = await sunoApiGenerate({
              apiKey,
              model,
              title: song.title,
              lyrics: prompt,
              style: song.songDescription,
              instrumental: false,
              callbackUrl
            });
            taskId = gen.taskId;
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: "PENDING",
              outputDirOk,
              outputDirAlt
            });
          }
          const r = await sunoApiTryGetTracks(apiKey, taskId);
          if (r.audioUrls.length >= 2) {
            const okUrl = String(r.audioUrls[0] || "").trim();
            const altUrl = String(r.audioUrls[1] || "").trim();
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: String(r.status || "SUCCESS"),
              audioUrlOk: okUrl,
              audioUrlAlt: altUrl,
              outputDirOk,
              outputDirAlt
            });
            const trackNo = typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : i + 1;
            const pathsOk = buildSunoOutputPaths({ outputDir: outputDirOk, title: song.title, trackNo });
            const pathsAlt = buildSunoOutputPaths({ outputDir: outputDirAlt, title: song.title, trackNo });
            await downloadToFile(okUrl, pathsOk.ok);
            await downloadToFile(altUrl, pathsAlt.alt);
          } else {
            await upsertSunoTask(db, {
              requestHash,
              songUid: song.id,
              batchId: song.batchId ?? batchId,
              trackNo: typeof song.batchIndex === "number" && Number.isFinite(song.batchIndex) ? Math.floor(song.batchIndex) : null,
              model,
              title: song.title,
              style: song.songDescription,
              instrumental: false,
              taskId,
              status: String(r.status || "PENDING"),
              outputDirOk,
              outputDirAlt
            });
            deferred += 1;
          }
          break;
        } catch (e) {
          lastErr = e;
          await sleep(1500 * (attempt + 1));
        }
      }
      if (lastErr) {
        const msg = lastErr instanceof Error ? lastErr.message : "Suno API generation failed";
        throw new Error(msg);
      }
    }
    if (deferred > 0) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: `Suno API: ${deferred} task(s) processing; will auto-download in background`,
        progress: 98
      });
    }
    if (job.payload.mergeEnabled && deferred === 0) {
      const mergedOkDir = path4.join(outputDirOk, "merge");
      const mergedAltDir = path4.join(outputDirAlt, "merge");
      const ffmpegPath = String(job.payload.ffmpegPath || "").trim();
      if (!ffmpegPath) throw new Error("FFmpeg path is not configured");
      const chunkSize = Number(job.payload.mergeGroupSize ?? 0);
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merging OK tracks\u2026",
        progress: 92
      });
      await mergeAudioByVersion({
        versionType: "OK",
        chunkSize,
        inputDir: outputDirOk,
        outputDir: mergedOkDir,
        ffmpegPath
      });
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merging ALT tracks\u2026",
        progress: 96
      });
      await mergeAudioByVersion({
        versionType: "ALT",
        chunkSize,
        inputDir: outputDirAlt,
        outputDir: mergedAltDir,
        ffmpegPath
      });
    } else if (job.payload.mergeEnabled && deferred > 0) {
      emitEvent(this.emitter, {
        jobId: job.jobId,
        jobType: "suno",
        status: "running",
        message: "Merge skipped (waiting for pending Suno downloads)",
        progress: 99
      });
    }
  }
  async runGenerate(job) {
    if (job.payload.jobType !== "workflow") return void 0;
    const songDraftProvider = job.payload.songDraftProvider ?? "deepseek";
    const deepseekApiKey = songDraftProvider === "deepseek" ? job.payload.deepseekApiKey || process.env.DEEPSEEK_API_KEY : "";
    const slaiSongApiKey = songDraftProvider === "slai" ? job.payload.slaiSongApiKey || process.env.SLAI_SONG_API_KEY || process.env.SLAI_API_KEY : "";
    const slaiSongModel = String(job.payload.slaiSongModel || "").trim();
    if (songDraftProvider === "deepseek" && !deepseekApiKey) throw new Error("DeepSeek API key is not configured");
    if (songDraftProvider === "slai" && !slaiSongApiKey) throw new Error("SLAI Song API key is not configured");
    const description = job.payload.description ?? "";
    const structure = job.payload.structure ?? "";
    const language = job.payload.language ?? "English";
    const creativity = Number.isFinite(job.payload.creativity) ? job.payload.creativity : 55;
    const batchId = job.payload.batchId;
    const uniqueOpening = job.payload.uniqueOpening;
    const strictLevel = job.payload.strictLevel;
    const historyWindow = job.payload.uniquenessHistoryWindow ?? 100;
    const db = job.payload.db;
    const descriptionTitle = job.payload.descriptionTitle ?? "";
    const structureTitle = job.payload.structureTitle ?? "";
    const profileOkId = job.payload.profileOkId;
    const profileAltId = job.payload.profileAltId;
    const sunoAutoSubmit = Boolean(job.payload.sunoAutoSubmit);
    const sunoApiKey = String(job.payload.sunoApiKey || "").trim();
    const sunoCallbackUrl = String(job.payload.sunoCallbackUrl || "").trim();
    const sunoVersion = job.payload.sunoVersion ?? "v5.5";
    const sunoOutputDirOk = String(job.payload.sunoOutputDirOk || "").trim();
    const sunoOutputDirAlt = String(job.payload.sunoOutputDirAlt || "").trim() || sunoOutputDirOk;
    const batchIndex = typeof job.payload.batchIndex === "number" && Number.isFinite(job.payload.batchIndex) ? Math.floor(job.payload.batchIndex) : void 0;
    if (!db) throw new Error("Postgres database is not configured. Set Database settings and run Migrate.");
    cleanupBatchAlbums();
    const batchKey = batchId ?? job.jobId;
    const existingBatchAlbum = batchAlbumByBatchId.get(batchKey);
    const fixedAlbum = existingBatchAlbum?.album;
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "workflow",
      status: "running",
      message: "Writing the song\u2026",
      progress: 20,
      action: "generate"
    });
    console.log("[jobQueue] generate start", {
      jobId: job.jobId,
      provider: songDraftProvider,
      model: songDraftProvider === "slai" ? slaiSongModel || "gpt-5.5" : "deepseek-chat",
      language,
      creativity,
      descriptionChars: description.length,
      structureChars: structure.length,
      uniqueOpening: Boolean(uniqueOpening),
      strictLevel: strictLevel ?? 3,
      historyWindow
    });
    const avoid = await getAvoidLists(db, historyWindow);
    let draft = null;
    let lastDraftError = null;
    let forcedAlbum = fixedAlbum;
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      const attemptStartedAt = Date.now();
      const picked = await getPooled(db, { opening: Boolean(uniqueOpening), title: true, album: !forcedAlbum });
      if (!picked.title) throw new Error("Title pool is empty. Seed Postgres table title_pool.");
      if (!forcedAlbum) {
        if (!picked.album) throw new Error("Album pool is empty. Seed Postgres table album_pool.");
        forcedAlbum = picked.album;
        batchAlbumByBatchId.set(batchKey, { album: forcedAlbum, createdAtMs: Date.now() });
      }
      const forcedOpening = uniqueOpening && picked.opening?.line1 && picked.opening?.line2 ? `${picked.opening.line1}
${picked.opening.line2}` : void 0;
      if (uniqueOpening && !forcedOpening) throw new Error("Opening pool is empty. Seed Postgres table opening_pairs.");
      try {
        console.log("[jobQueue] generate attempt", { jobId: job.jobId, attempt, provider: songDraftProvider });
        draft = songDraftProvider === "slai" ? await generateSongDraftWithSlai({
          apiKey: slaiSongApiKey,
          model: slaiSongModel || void 0,
          language,
          creativity,
          description,
          structure,
          uniqueOpening,
          strictLevel,
          avoidTitles: avoid.titles,
          avoidAlbums: avoid.albums,
          avoidOpenings: avoid.openings,
          forcedTitle: picked.title,
          forcedAlbum,
          forcedOpening
        }) : await generateSongDraftWithDeepSeek({
          apiKey: deepseekApiKey,
          language,
          creativity,
          description,
          structure,
          uniqueOpening,
          strictLevel,
          avoidTitles: avoid.titles,
          avoidAlbums: avoid.albums,
          avoidOpenings: avoid.openings,
          forcedTitle: picked.title,
          forcedAlbum,
          forcedOpening
        });
        console.log("[jobQueue] generate draft ok", {
          jobId: job.jobId,
          attempt,
          provider: songDraftProvider,
          ms: Date.now() - attemptStartedAt,
          titleChars: draft.title.length,
          albumChars: draft.album.length,
          lyricsChars: draft.lyricsRaw.length
        });
        break;
      } catch (e) {
        console.log("[jobQueue] generate attempt failed", {
          jobId: job.jobId,
          attempt,
          provider: songDraftProvider,
          ms: Date.now() - attemptStartedAt,
          message: e instanceof Error ? e.message : String(e || "")
        });
        lastDraftError = e;
        draft = null;
      }
    }
    if (!draft) {
      const msg = lastDraftError instanceof Error ? lastDraftError.message : String(lastDraftError || "");
      throw new Error(`Failed to generate song draft after retries${msg ? `: ${msg}` : ""}`);
    }
    const lyricsPolished = draft.lyricsRaw;
    emitEvent(this.emitter, {
      jobId: job.jobId,
      jobType: "workflow",
      status: "running",
      message: "Saving your song\u2026",
      progress: 90,
      action: "generate"
    });
    const createdAt = (/* @__PURE__ */ new Date()).toISOString();
    const songUid = randomUUID2();
    if (db) {
      await upsertSong(db, {
        songUid,
        title: draft.title,
        album: draft.album,
        lyricsRaw: draft.lyricsRaw,
        lyricsPolished,
        songDescription: description,
        songStructure: structure,
        language,
        creativity,
        batchId,
        batchIndex,
        status: "generated",
        createdAtIso: createdAt
      });
      await insertHistory(db, { kind: "song_generated", message: `${draft.title} / ${draft.album}`, songUid });
    }
    const outSong = {
      id: songUid,
      title: draft.title,
      album: draft.album,
      lyricsRaw: draft.lyricsRaw,
      lyricsPolished,
      batchIndex,
      songDescriptionTitle: descriptionTitle,
      songStructureTitle: structureTitle,
      songDescription: description,
      songStructure: structure,
      profileOkId,
      profileAltId,
      language,
      creativity,
      batchId,
      createdAt
    };
    if (sunoAutoSubmit && db && sunoOutputDirOk) {
      const model = sunoVersion === "v5" ? "V5" : "V5_5";
      this.sunoSubmitter.enqueue({
        jobId: job.jobId,
        db,
        apiKey: sunoApiKey,
        callbackUrl: sunoCallbackUrl,
        model,
        song: outSong,
        outputDirOk: sunoOutputDirOk,
        outputDirAlt: sunoOutputDirAlt
      });
    }
    return outSong;
  }
};

// electron/db/testPostgres.ts
import * as pg4 from "pg";
async function testPostgresConnection(opts) {
  const client = new pg4.Client({
    host: opts.host,
    port: opts.port,
    user: opts.user,
    password: opts.password,
    database: opts.database
  });
  const timeoutMs = opts.timeoutMs ?? 5e3;
  const timeout = setTimeout(() => {
    void client.end();
  }, timeoutMs);
  try {
    await client.connect();
    const res = await client.query("select 1 as ok");
    const ok = res?.rows?.[0]?.ok === 1;
    return { ok, message: ok ? "Connection OK" : "Connected but test query failed" };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : "Connection failed" };
  } finally {
    clearTimeout(timeout);
    await client.end().catch(() => void 0);
  }
}

// electron/db/migratePostgres.ts
import * as pg5 from "pg";
var MIGRATION_SQL = `
create table if not exists songs (
  id serial primary key,
  song_uid text,
  title text,
  lyrics_raw text,
  lyrics_polished text,
  album text,
  song_description text,
  song_structure text,
  language text,
  creativity int,
  batch_id text,
  batch_index int,
  status text,
  created_at timestamp default now()
);

alter table songs add column if not exists song_uid text;
alter table songs add column if not exists language text;
alter table songs add column if not exists creativity int;
alter table songs add column if not exists batch_id text;
alter table songs add column if not exists batch_index int;
create unique index if not exists ux_songs_song_uid on songs(song_uid);
create index if not exists idx_songs_created_at on songs(created_at desc);

alter table songs add column if not exists song_description text;
alter table songs add column if not exists song_structure text;

create table if not exists history (
  id serial primary key,
  kind text,
  song_uid text,
  message text,
  created_at timestamp default now()
);

create index if not exists idx_history_created_at on history(created_at desc);

create table if not exists images (
  id serial primary key,
  song_id int,
  type text,
  path text,
  created_at timestamp default now()
);

create table if not exists car_models (
  id serial primary key,
  uid text,
  make text,
  model text,
  trim text,
  year int,
  category text,
  updated_at timestamp default now()
);

alter table car_models add column if not exists uid text;
alter table car_models add column if not exists updated_at timestamp default now();
create unique index if not exists ux_car_models_uid on car_models(uid);

create table if not exists image_samples (
  id serial primary key,
  file_path text,
  tags text[],
  created_at timestamp default now()
);

create table if not exists prompt_templates (
  id serial primary key,
  uid text,
  name text,
  content text,
  tags text[],
  scene text,
  negative_prompt text,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table prompt_templates add column if not exists uid text;
alter table prompt_templates add column if not exists updated_at timestamp default now();
alter table prompt_templates add column if not exists scene text;
alter table prompt_templates add column if not exists negative_prompt text;
update prompt_templates set scene = content where (scene is null or scene = '') and (content is not null and content <> '');
update prompt_templates set negative_prompt = content where (negative_prompt is null or negative_prompt = '') and (content is not null and content <> '') and (tags is not null) and array_position(tags, 'negative') is not null;
update prompt_templates set scene = '' where (tags is not null) and array_position(tags, 'negative') is not null;
create unique index if not exists ux_prompt_templates_uid on prompt_templates(uid);

create table if not exists text_styles (
  id serial primary key,
  uid text,
  name text,
  title text,
  subtitle text,
  subtitle2 text,
  prompt text,
  opacity float,
  position text,
  updated_at timestamp default now()
);

alter table text_styles add column if not exists uid text;
alter table text_styles add column if not exists subtitle2 text;
alter table text_styles add column if not exists prompt text;
alter table text_styles add column if not exists preset_id text;
alter table text_styles add column if not exists palette_id text;
alter table text_styles add column if not exists updated_at timestamp default now();
create unique index if not exists ux_text_styles_uid on text_styles(uid);

create table if not exists song_structures (
  id serial primary key,
  uid text,
  name text,
  content text,
  match_key text,
  updated_at timestamp default now()
);

alter table song_structures add column if not exists uid text;
alter table song_structures add column if not exists match_key text;
create unique index if not exists ux_song_structures_uid on song_structures(uid);

create table if not exists song_descriptions (
  id serial primary key,
  uid text,
  name text,
  content text,
  match_key text,
  updated_at timestamp default now()
);

alter table song_descriptions add column if not exists uid text;
alter table song_descriptions add column if not exists match_key text;
create unique index if not exists ux_song_descriptions_uid on song_descriptions(uid);

create table if not exists automation_logs (
  id serial primary key,
  song_id int,
  status text,
  message text,
  created_at timestamp default now()
);

create table if not exists opening_pairs (
  id serial primary key,
  line1 text,
  line2 text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_opening_pairs_norm on opening_pairs(norm);
create index if not exists idx_opening_pairs_used on opening_pairs(used_count, id);

create table if not exists title_pool (
  id serial primary key,
  title text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_title_pool_norm on title_pool(norm);
create index if not exists idx_title_pool_used on title_pool(used_count, id);

create table if not exists album_pool (
  id serial primary key,
  album text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_album_pool_norm on album_pool(norm);
create index if not exists idx_album_pool_used on album_pool(used_count, id);

create table if not exists app_settings (
  key text primary key,
  value text not null,
  updated_at timestamp default now()
);

alter table app_settings add column if not exists updated_at timestamp default now();

create table if not exists app_json (
  key text primary key,
  value jsonb not null,
  updated_at timestamp default now()
);

alter table app_json add column if not exists updated_at timestamp default now();

create table if not exists profiles (
  uid text primary key,
  name text not null,
  folder_name text not null,
  run_prefix text not null default '',
  logo_path text not null default '',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table profiles add column if not exists uid text;
alter table profiles add column if not exists folder_name text;
alter table profiles add column if not exists run_prefix text not null default '';
alter table profiles add column if not exists logo_path text not null default '';
alter table profiles add column if not exists updated_at timestamp default now();
create unique index if not exists ux_profiles_uid on profiles(uid);

create table if not exists video_templates (
  uid text primary key,
  name text not null,
  source text not null default 'user',
  template jsonb not null,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table video_templates add column if not exists uid text;
alter table video_templates add column if not exists source text not null default 'user';
alter table video_templates add column if not exists updated_at timestamp default now();
create unique index if not exists ux_video_templates_uid on video_templates(uid);

create table if not exists suno_tasks (
  id serial primary key,
  request_hash text,
  song_uid text,
  batch_id text,
  track_no int,
  model text,
  title text,
  style text,
  instrumental boolean,
  task_id text,
  status text,
  audio_url_ok text,
  audio_url_alt text,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create unique index if not exists ux_suno_tasks_request_hash on suno_tasks(request_hash);
create index if not exists idx_suno_tasks_song_uid on suno_tasks(song_uid);
create index if not exists idx_suno_tasks_task_id on suno_tasks(task_id);
alter table suno_tasks add column if not exists request_hash text;
alter table suno_tasks add column if not exists song_uid text;
alter table suno_tasks add column if not exists batch_id text;
alter table suno_tasks add column if not exists track_no int;
alter table suno_tasks add column if not exists model text;
alter table suno_tasks add column if not exists title text;
alter table suno_tasks add column if not exists style text;
alter table suno_tasks add column if not exists instrumental boolean;
alter table suno_tasks add column if not exists task_id text;
alter table suno_tasks add column if not exists status text;
alter table suno_tasks add column if not exists audio_url_ok text;
alter table suno_tasks add column if not exists audio_url_alt text;
alter table suno_tasks add column if not exists output_dir text;
alter table suno_tasks add column if not exists output_dir_ok text;
alter table suno_tasks add column if not exists output_dir_alt text;
alter table suno_tasks add column if not exists updated_at timestamp default now();
create unique index if not exists ux_suno_tasks_request_hash on suno_tasks(request_hash);
create index if not exists idx_suno_tasks_song_uid on suno_tasks(song_uid);
create index if not exists idx_suno_tasks_task_id on suno_tasks(task_id);

alter table opening_pairs add column if not exists norm text;
alter table opening_pairs add column if not exists used_count int not null default 0;
alter table title_pool add column if not exists norm text;
alter table title_pool add column if not exists used_count int not null default 0;
alter table album_pool add column if not exists norm text;
alter table album_pool add column if not exists used_count int not null default 0;

create unique index if not exists ux_opening_pairs_norm on opening_pairs(norm);
create unique index if not exists ux_title_pool_norm on title_pool(norm);
create unique index if not exists ux_album_pool_norm on album_pool(norm);
`;
function assertSafeDbName(name) {
  if (!/^[a-zA-Z0-9_]+$/.test(name)) throw new Error("Database name must be alphanumeric/underscore");
}
async function connect4(cfg) {
  const client = new pg5.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function ensureDatabaseAndMigrate(cfg) {
  assertSafeDbName(cfg.database);
  let client = null;
  try {
    client = await connect4(cfg);
  } catch (e) {
    const err = e;
    if (err.code !== "3D000") return { ok: false, message: err.message ?? "Connection failed" };
    const adminDb = cfg.database === "postgres" ? "template1" : "postgres";
    const admin = await connect4({ ...cfg, database: adminDb });
    try {
      const db = cfg.database.replace(/"/g, '""');
      await admin.query(`create database "${db}"`);
    } catch (e2) {
      await admin.end().catch(() => void 0);
      return { ok: false, message: e2 instanceof Error ? e2.message : "Create database failed" };
    }
    await admin.end().catch(() => void 0);
    try {
      client = await connect4(cfg);
    } catch (e3) {
      return { ok: false, message: e3 instanceof Error ? e3.message : "Re-connect failed" };
    }
  }
  try {
    await client.query("begin");
    await client.query(MIGRATION_SQL);
    await client.query("commit");
    return { ok: true, message: "Migrations applied" };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    return { ok: false, message: e instanceof Error ? e.message : "Migration failed" };
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/ffmpeg/downloadFfmpeg.ts
import { promises as fs4 } from "node:fs";
import path5 from "node:path";
import AdmZip from "adm-zip";
async function ensureDir(p) {
  await fs4.mkdir(p, { recursive: true });
}
async function writeFile(p, data) {
  await ensureDir(path5.dirname(p));
  await fs4.writeFile(p, Buffer.from(data));
}
async function exists(p) {
  try {
    await fs4.access(p);
    return true;
  } catch {
    return false;
  }
}
async function findFfmpegExe(rootDir) {
  const stack = [rootDir];
  while (stack.length) {
    const dir = stack.pop();
    if (!dir) continue;
    let entries = [];
    try {
      entries = await fs4.readdir(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = path5.join(dir, e.name);
      if (e.isDirectory()) stack.push(full);
      else if (e.isFile() && e.name.toLowerCase() === "ffmpeg.exe") return full;
    }
  }
  return null;
}
async function downloadFfmpeg(opts) {
  const url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip";
  const installDir = path5.resolve(opts.installDir);
  const tmpDir = path5.join(installDir, ".mg-tmp");
  await ensureDir(tmpDir);
  const zipPath = path5.join(tmpDir, "ffmpeg.zip");
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Download failed (${res.status}): ${body.slice(0, 200)}`);
  }
  const buf = await res.arrayBuffer();
  await writeFile(zipPath, buf);
  const targetDir = path5.join(installDir, "ffmpeg");
  await ensureDir(targetDir);
  const zip = new AdmZip(zipPath);
  zip.extractAllTo(targetDir, true);
  const ffmpegExe = await findFfmpegExe(targetDir);
  if (!ffmpegExe || !await exists(ffmpegExe)) throw new Error("ffmpeg.exe not found after extraction");
  await fs4.rm(tmpDir, { recursive: true, force: true }).catch(() => void 0);
  return { ok: true, ffmpegPath: ffmpegExe, installDir: targetDir };
}

// electron/fs/pathUtils.ts
import { promises as fs5 } from "node:fs";
async function pathExists(p) {
  try {
    await fs5.access(p);
    return true;
  } catch {
    return false;
  }
}

// electron/ai/openaiSong.ts
async function chatCompletion3(opts) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${opts.apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: opts.model,
      messages: opts.messages,
      temperature: opts.temperature ?? 0.7
    })
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`OpenAI error ${res.status}: ${body.slice(0, 400)}`);
  }
  const json = await res.json();
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("OpenAI returned empty content");
  return content;
}
async function polishLyricsWithOpenAI(input) {
  const model = input.model ?? "gpt-4o-mini";
  const strength = Math.max(0, Math.min(100, input.strength));
  const temperature = 0.15 + strength / 100 * 0.55;
  const polishedLyrics = await chatCompletion3({
    apiKey: input.apiKey,
    model,
    temperature,
    messages: [
      {
        role: "system",
        content: "Polish song lyrics: improve flow, rhythm, and clarity while preserving meaning. Keep section labels like [Verse], [Chorus] and keep line breaks. Return ONLY the polished lyrics text."
      },
      { role: "user", content: input.lyrics }
    ]
  });
  return polishedLyrics.trim();
}

// electron/main.ts
import { promises as fs12 } from "node:fs";

// electron/dbConfig.ts
import path6 from "node:path";
import { promises as fs6 } from "node:fs";
function getDbConfigPath(opts) {
  const baseDir = opts.isPackaged ? path6.dirname(opts.execPath) : opts.appPath;
  return path6.join(baseDir, "db-connection.json");
}
async function readDbConfig(filePath) {
  try {
    const raw = await fs6.readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    const host = String(parsed.host ?? "").trim();
    const user = String(parsed.user ?? "").trim();
    const database = String(parsed.database ?? "").trim();
    const port = Number(parsed.port ?? 0);
    const password = String(parsed.password ?? "");
    if (!host || !user || !database || !Number.isFinite(port) || port <= 0) return null;
    return { host, port, user, password, database };
  } catch {
    return null;
  }
}
async function writeDbConfig(filePath, cfg) {
  const out = {
    host: String(cfg.host || "").trim(),
    port: Math.max(1, Math.floor(Number(cfg.port) || 5432)),
    user: String(cfg.user || "").trim(),
    password: String(cfg.password || ""),
    database: String(cfg.database || "").trim()
  };
  await fs6.mkdir(path6.dirname(filePath), { recursive: true });
  await fs6.writeFile(filePath, JSON.stringify(out, null, 2), "utf-8");
}

// electron/db/appJsonStore.ts
import * as pg6 from "pg";
async function connect5(cfg) {
  const client = new pg6.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function getAppJson(cfg, key) {
  const client = await connect5(cfg);
  try {
    const r = await client.query("select value from app_json where key = $1", [key]);
    if (!r.rows.length) return null;
    return r.rows[0].value;
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function setAppJson(cfg, key, value) {
  const client = await connect5(cfg);
  try {
    await client.query(
      `insert into app_json(key, value, updated_at) values ($1, $2::jsonb, now())
       on conflict (key) do update set value = excluded.value, updated_at = now()`,
      [key, JSON.stringify(value)]
    );
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/db/profileStore.ts
import * as pg7 from "pg";
async function connect6(cfg) {
  const client = new pg7.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function listProfiles(cfg) {
  const client = await connect6(cfg);
  try {
    const r = await client.query(
      "select uid, name, folder_name, run_prefix, logo_path, created_at, updated_at from profiles order by created_at asc"
    );
    return r.rows.map((x) => ({
      id: String(x.uid),
      name: String(x.name ?? ""),
      folderName: String(x.folder_name ?? ""),
      runPrefix: String(x.run_prefix ?? ""),
      logoPath: String(x.logo_path ?? ""),
      createdAt: new Date(x.created_at).toISOString(),
      updatedAt: new Date(x.updated_at).toISOString()
    }));
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function syncProfiles(cfg, items) {
  const client = await connect6(cfg);
  try {
    await client.query("begin");
    if (!items.length) {
      await client.query("delete from profiles");
    } else {
      await client.query("delete from profiles where uid <> all($1::text[])", [items.map((x) => x.id)]);
    }
    for (const p of items) {
      await client.query(
        `insert into profiles(uid, name, folder_name, run_prefix, logo_path, created_at, updated_at)
         values ($1,$2,$3,$4,$5, now(), now())
         on conflict (uid) do update set
           name = excluded.name,
           folder_name = excluded.folder_name,
           run_prefix = excluded.run_prefix,
           logo_path = excluded.logo_path,
           updated_at = now()`,
        [p.id, p.name, p.folderName, p.runPrefix, p.logoPath]
      );
    }
    await client.query("commit");
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/db/videoTemplateStore.ts
import * as pg8 from "pg";
async function connect7(cfg) {
  const client = new pg8.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
async function listVideoTemplates(cfg) {
  const client = await connect7(cfg);
  try {
    const r = await client.query("select uid, name, source, template, updated_at from video_templates order by name asc");
    return r.rows.map((x) => ({
      id: String(x.uid),
      name: String(x.name ?? ""),
      source: String(x.source ?? "user") === "builtin" ? "builtin" : "user",
      template: x.template,
      updatedAt: new Date(x.updated_at).toISOString()
    }));
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function getVideoTemplate(cfg, id) {
  const client = await connect7(cfg);
  try {
    const r = await client.query("select uid, name, source, template, updated_at from video_templates where uid = $1", [id]);
    if (!r.rows.length) return null;
    const x = r.rows[0];
    return {
      id: String(x.uid),
      name: String(x.name ?? ""),
      source: String(x.source ?? "user") === "builtin" ? "builtin" : "user",
      template: x.template,
      updatedAt: new Date(x.updated_at).toISOString()
    };
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function upsertVideoTemplate(cfg, input) {
  const client = await connect7(cfg);
  try {
    await client.query(
      `insert into video_templates(uid, name, source, template, created_at, updated_at)
       values ($1,$2,$3,$4::jsonb, now(), now())
       on conflict (uid) do update set
         name = excluded.name,
         source = excluded.source,
         template = excluded.template,
         updated_at = now()`,
      [input.id, input.name, input.source, JSON.stringify(input.template)]
    );
  } finally {
    await client.end().catch(() => void 0);
  }
}
async function deleteVideoTemplate(cfg, id) {
  const client = await connect7(cfg);
  try {
    await client.query("delete from video_templates where uid = $1", [id]);
  } finally {
    await client.end().catch(() => void 0);
  }
}

// electron/ai/openaiImage.ts
import { nativeImage } from "electron";
function scoreImageLumaStddev(input) {
  const img = nativeImage.createFromPath(input.filePath);
  if (img.isEmpty()) return 0;
  const size = img.getSize();
  if (!size.width || !size.height) return 0;
  const rx0 = input.region?.x0 ?? 0.22;
  const ry0 = input.region?.y0 ?? 0.22;
  const rx1 = input.region?.x1 ?? 0.78;
  const ry1 = input.region?.y1 ?? 0.78;
  const x0 = Math.max(0, Math.min(size.width - 1, Math.floor(size.width * rx0)));
  const y0 = Math.max(0, Math.min(size.height - 1, Math.floor(size.height * ry0)));
  const x1 = Math.max(x0 + 1, Math.min(size.width, Math.floor(size.width * rx1)));
  const y1 = Math.max(y0 + 1, Math.min(size.height, Math.floor(size.height * ry1)));
  const cropped = img.crop({ x: x0, y: y0, width: x1 - x0, height: y1 - y0 });
  const csize = cropped.getSize();
  const bitmap = cropped.toBitmap();
  if (!bitmap.length || !csize.width || !csize.height) return 0;
  const stride = csize.width * 4;
  const step = 4;
  let n = 0;
  let sum = 0;
  let sum2 = 0;
  for (let y = 0; y < csize.height; y += step) {
    const row = y * stride;
    for (let x = 0; x < csize.width; x += step) {
      const i = row + x * 4;
      const r = bitmap[i] ?? 0;
      const g = bitmap[i + 1] ?? 0;
      const b = bitmap[i + 2] ?? 0;
      const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      n += 1;
      sum += l;
      sum2 += l * l;
    }
  }
  if (n <= 1) return 0;
  const mean = sum / n;
  const variance = Math.max(0, sum2 / n - mean * mean);
  return Math.sqrt(variance);
}

// electron/ai/slaiImage.ts
import { promises as fs7 } from "node:fs";
import path7 from "node:path";
import { nativeImage as nativeImage2 } from "electron";
function parseResolution(resolution) {
  const m = String(resolution).match(/^(\d+)x(\d+)$/);
  const w = m ? Math.max(1, Number(m[1])) : 1920;
  const h = m ? Math.max(1, Number(m[2])) : 1080;
  return { w, h };
}
function toCoverPngBytes(input) {
  const img = nativeImage2.createFromBuffer(input.pngBytes);
  if (img.isEmpty()) return input.pngBytes;
  const size = img.getSize();
  if (!size.width || !size.height) return input.pngBytes;
  const scale = Math.max(input.width / size.width, input.height / size.height);
  const rw = Math.max(1, Math.round(size.width * scale));
  const rh = Math.max(1, Math.round(size.height * scale));
  const resized = img.resize({ width: rw, height: rh, quality: "best" });
  const rsize = resized.getSize();
  if (!rsize.width || !rsize.height) return input.pngBytes;
  const x = Math.max(0, Math.floor((rsize.width - input.width) / 2));
  const y = Math.max(0, Math.floor((rsize.height - input.height) / 2));
  const cropW = Math.min(input.width, rsize.width);
  const cropH = Math.min(input.height, rsize.height);
  const cropped = resized.crop({ x, y, width: cropW, height: cropH });
  const out = cropped.toPNG();
  return out.length ? out : input.pngBytes;
}
function toPngBytes(filePath) {
  const img = nativeImage2.createFromPath(filePath);
  if (img.isEmpty()) return null;
  const bytes = img.toPNG();
  return bytes.length ? bytes : null;
}
function toDataUrl(input) {
  const ext = path7.extname(input.filePath).toLowerCase();
  const mime = ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : ext === ".webp" ? "image/webp" : "image/png";
  const bytes = input.bytes?.length ? input.bytes : null;
  if (!bytes) return null;
  return `data:${mime};base64,${bytes.toString("base64")}`;
}
async function generateWithSlai(input) {
  const startedAt = Date.now();
  const apiKey = String(input.apiKey || "").trim();
  if (!apiKey) throw new Error("SLAI IMG API key is not configured");
  const model = String(input.model || "").trim() || "cgpt-web/gpt-5.5-pro";
  const prompt = String(input.prompt || "").trim();
  if (!prompt) throw new Error("Prompt is empty");
  const imageFilePath = String(input.imageFilePath || "").trim();
  if (!imageFilePath) throw new Error("Base image is missing");
  const bytes = toPngBytes(imageFilePath) ?? await fs7.readFile(imageFilePath);
  const imageUrl = toDataUrl({ filePath: imageFilePath, bytes });
  if (!imageUrl) throw new Error("Failed to read base image");
  const aspectRatio = input.resolution === "1080x1920" ? "9:16" : "16:9";
  const endpoints = ["https://api.slai.shop/v1/images/generations", "https://api-img.slai.shop/v1/images/generations"];
  console.log("[slaiImage] images/generations start", {
    model,
    aspectRatio,
    promptChars: prompt.length,
    imageFile: path7.basename(imageFilePath),
    endpoints
  });
  let raw = "";
  let lastStatus = 0;
  let lastUrl = endpoints[0] ?? "";
  let okResp = null;
  for (const endpoint of endpoints) {
    lastUrl = endpoint;
    const t0 = Date.now();
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model,
        prompt,
        image_url: imageUrl,
        aspect_ratio: aspectRatio
      })
    });
    lastStatus = resp.status;
    raw = await resp.text();
    console.log("[slaiImage] images/generations response", { endpoint, status: resp.status, ok: resp.ok, ms: Date.now() - t0 });
    if (resp.ok) {
      okResp = resp;
      break;
    }
    if (resp.status === 404 || resp.status === 405) continue;
    let msg = `SLAI image generation failed (${resp.status})`;
    try {
      const j = JSON.parse(raw);
      if (j?.error?.message) msg = j.error.message;
    } catch {
      if (raw.trim()) msg = raw.slice(0, 220);
    }
    console.log("[slaiImage] images/generations error body", { endpoint, status: resp.status, bodyPreview: raw.slice(0, 220) });
    throw new Error(msg);
  }
  if (!okResp) {
    let msg = `SLAI image generation failed (${lastStatus || "unknown"})`;
    try {
      const j = JSON.parse(raw);
      if (j?.error?.message) msg = j.error.message;
    } catch {
      if (raw.trim()) msg = raw.slice(0, 220);
    }
    console.log("[slaiImage] images/generations failed after fallbacks", { lastUrl, lastStatus, bodyPreview: raw.slice(0, 220) });
    throw new Error(`${msg} (endpoint: ${lastUrl})`);
  }
  let pngBytes = null;
  let imageOutUrl = "";
  try {
    const j = JSON.parse(raw);
    const row = j.data?.[0] ?? null;
    const b64 = String(row?.b64_json ?? j.b64_json ?? "").trim();
    if (b64) pngBytes = Buffer.from(b64, "base64");
    imageOutUrl = String(row?.url ?? j.url ?? "").trim();
  } catch {
  }
  if (!pngBytes?.length && imageOutUrl) {
    const imgResp = await fetch(imageOutUrl);
    if (!imgResp.ok) throw new Error(`Failed to download image (${imgResp.status})`);
    const ab = await imgResp.arrayBuffer();
    pngBytes = Buffer.from(ab);
  }
  if (!pngBytes?.length) throw new Error("SLAI returned no image data");
  console.log("[slaiImage] images/generations done", { ms: Date.now() - startedAt, pngBytes: pngBytes.length });
  const meta = {
    provider: "slai",
    endpoint: "images/generations",
    model,
    attempts: 1,
    size: aspectRatio
  };
  return { pngBytes, meta };
}
async function generateBackgroundWithSlai(input) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");
  const { pngBytes, meta } = await generateWithSlai({
    apiKey: input.apiKey,
    model: input.model,
    prompt: input.prompt,
    imageFilePath: input.sampleFilePath,
    resolution: input.resolution
  });
  const target = parseResolution(input.resolution);
  const outBytes = toCoverPngBytes({ pngBytes, width: target.w, height: target.h });
  const outDir = path7.join(outRoot, "backgrounds");
  await fs7.mkdir(outDir, { recursive: true });
  const safeSize = input.resolution;
  const outPath = path7.join(outDir, `background_${Date.now()}_${safeSize}.png`);
  await fs7.writeFile(outPath, outBytes);
  return { filePath: outPath, meta };
}
async function generateThumbnailWithSlai(input) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");
  const { pngBytes, meta } = await generateWithSlai({
    apiKey: input.apiKey,
    model: input.model,
    prompt: input.prompt,
    imageFilePath: input.backgroundFilePath,
    resolution: input.resolution
  });
  const target = parseResolution(input.resolution);
  const outBytes = toCoverPngBytes({ pngBytes, width: target.w, height: target.h });
  const outDir = path7.join(outRoot, "thumbnails");
  await fs7.mkdir(outDir, { recursive: true });
  const safeSize = input.resolution;
  const outPath = path7.join(outDir, `thumbnail_${Date.now()}_${safeSize}.png`);
  await fs7.writeFile(outPath, outBytes);
  return { filePath: outPath, meta };
}

// electron/db/contentStore.ts
import * as pg9 from "pg";
async function connect8(cfg) {
  const client = new pg9.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database
  });
  await client.connect();
  return client;
}
function nowIso3() {
  return (/* @__PURE__ */ new Date()).toISOString();
}
async function listPromptTemplates(cfg) {
  const client = await connect8(cfg);
  try {
    await client.query("update prompt_templates set uid = concat('tpl-', id) where uid is null");
    const res = await client.query(
      "select uid, name, scene, negative_prompt, coalesce(updated_at, created_at) as updated_at from prompt_templates order by coalesce(updated_at, created_at) desc, id desc"
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      scene: String(r.scene ?? ""),
      negativePrompt: String(r.negative_prompt ?? ""),
      updatedAt: new Date(r.updated_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function listCarModels(cfg) {
  const client = await connect8(cfg);
  try {
    await client.query("update car_models set uid = concat('car-', id) where uid is null");
    const res = await client.query(
      "select uid, make, model, trim, year, category, updated_at from car_models order by updated_at desc, id desc"
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      make: String(r.make ?? ""),
      model: String(r.model ?? ""),
      trim: String(r.trim ?? ""),
      year: Number(r.year ?? 0),
      category: String(r.category ?? ""),
      updatedAt: new Date(r.updated_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function upsertCarModel(cfg, item) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query(
      "insert into car_models(uid, make, model, trim, year, category, updated_at) values ($1,$2,$3,$4,$5,$6,$7) on conflict(uid) do update set make=excluded.make, model=excluded.model, trim=excluded.trim, year=excluded.year, category=excluded.category, updated_at=excluded.updated_at",
      [item.id, item.make, item.model, item.trim, item.year, item.category, updatedAt]
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}
async function deleteCarModel(cfg, id) {
  const client = await connect8(cfg);
  try {
    await client.query("delete from car_models where uid = $1", [id]);
    return { ok: true };
  } finally {
    await client.end();
  }
}
async function bulkUpsertCarModels(cfg, items) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query("begin");
    for (let i = 0; i < items.length; i += 500) {
      const chunk2 = items.slice(i, i + 500);
      const values = [];
      const parts = [];
      for (let j = 0; j < chunk2.length; j += 1) {
        const it = chunk2[j];
        const idx = j * 7;
        parts.push(`($${idx + 1},$${idx + 2},$${idx + 3},$${idx + 4},$${idx + 5},$${idx + 6},$${idx + 7})`);
        values.push(it.id, it.make, it.model, it.trim, it.year, it.category, updatedAt);
      }
      await client.query(
        `insert into car_models(uid, make, model, trim, year, category, updated_at)
         values ${parts.join(",")}
         on conflict(uid) do update set
           make=excluded.make,
           model=excluded.model,
           trim=excluded.trim,
           year=excluded.year,
           category=excluded.category,
           updated_at=excluded.updated_at`,
        values
      );
    }
    await client.query("commit");
    return { ok: true, updatedAt };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end();
  }
}
async function upsertPromptTemplate(cfg, item) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query(
      "insert into prompt_templates(uid, name, scene, negative_prompt, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, scene=excluded.scene, negative_prompt=excluded.negative_prompt, updated_at=excluded.updated_at",
      [item.id, item.name, item.scene, item.negativePrompt, updatedAt]
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}
async function deletePromptTemplate(cfg, id) {
  const client = await connect8(cfg);
  try {
    await client.query("delete from prompt_templates where uid = $1", [id]);
    return { ok: true };
  } finally {
    await client.end();
  }
}
async function listSongStructures(cfg) {
  const client = await connect8(cfg);
  try {
    await client.query("update song_structures set uid = concat('struct-', id) where uid is null");
    const res = await client.query(
      "select uid, name, content, match_key, updated_at from song_structures order by updated_at desc, id desc"
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      text: String(r.content ?? ""),
      matchKey: String(r.match_key ?? ""),
      updatedAt: new Date(r.updated_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function upsertSongStructure(cfg, item) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query(
      "insert into song_structures(uid, name, content, match_key, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, content=excluded.content, match_key=excluded.match_key, updated_at=excluded.updated_at",
      [item.id, item.name, item.text, String(item.matchKey ?? ""), updatedAt]
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}
async function deleteSongStructure(cfg, id) {
  const client = await connect8(cfg);
  try {
    await client.query("delete from song_structures where uid = $1", [id]);
    return { ok: true };
  } finally {
    await client.end();
  }
}
async function listSongDescriptions(cfg) {
  const client = await connect8(cfg);
  try {
    await client.query("update song_descriptions set uid = concat('desc-', id) where uid is null");
    const res = await client.query(
      "select uid, name, content, match_key, updated_at from song_descriptions order by updated_at desc, id desc"
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      text: String(r.content ?? ""),
      matchKey: String(r.match_key ?? ""),
      updatedAt: new Date(r.updated_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function upsertSongDescription(cfg, item) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query(
      "insert into song_descriptions(uid, name, content, match_key, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, content=excluded.content, match_key=excluded.match_key, updated_at=excluded.updated_at",
      [item.id, item.name, item.text, String(item.matchKey ?? ""), updatedAt]
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}
async function deleteSongDescription(cfg, id) {
  const client = await connect8(cfg);
  try {
    await client.query("delete from song_descriptions where uid = $1", [id]);
    return { ok: true };
  } finally {
    await client.end();
  }
}
async function listTextStyles(cfg) {
  const client = await connect8(cfg);
  try {
    await client.query("update text_styles set uid = concat('style-', id) where uid is null");
    const res = await client.query(
      "select uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at from text_styles order by updated_at desc, id desc"
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      presetId: String(r.preset_id ?? "") || void 0,
      paletteId: String(r.palette_id ?? "") || void 0,
      title: String(r.title ?? ""),
      subtitle: String(r.subtitle ?? ""),
      subtitle2: String(r.subtitle2 ?? ""),
      prompt: String(r.prompt ?? ""),
      opacity: Number(r.opacity ?? 0.9),
      position: String(r.position ?? "center"),
      updatedAt: new Date(r.updated_at).toISOString()
    }));
  } finally {
    await client.end();
  }
}
async function upsertTextStyle(cfg, item) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query(
      "insert into text_styles(uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) on conflict(uid) do update set name=excluded.name, preset_id=excluded.preset_id, palette_id=excluded.palette_id, title=excluded.title, subtitle=excluded.subtitle, subtitle2=excluded.subtitle2, prompt=excluded.prompt, opacity=excluded.opacity, position=excluded.position, updated_at=excluded.updated_at",
      [
        item.id,
        item.name,
        String(item.presetId ?? ""),
        String(item.paletteId ?? ""),
        item.title,
        item.subtitle,
        item.subtitle2,
        item.prompt,
        item.opacity,
        item.position,
        updatedAt
      ]
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}
async function deleteTextStyle(cfg, id) {
  const client = await connect8(cfg);
  try {
    await client.query("delete from text_styles where uid = $1", [id]);
    return { ok: true };
  } finally {
    await client.end();
  }
}
async function bulkUpsertTextStyles(cfg, items) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query("begin");
    for (let i = 0; i < items.length; i += 250) {
      const chunk2 = items.slice(i, i + 250);
      const values = [];
      const parts = [];
      for (let j = 0; j < chunk2.length; j += 1) {
        const it = chunk2[j];
        const idx = j * 11;
        parts.push(
          `($${idx + 1},$${idx + 2},$${idx + 3},$${idx + 4},$${idx + 5},$${idx + 6},$${idx + 7},$${idx + 8},$${idx + 9},$${idx + 10},$${idx + 11})`
        );
        values.push(
          it.id,
          it.name,
          String(it.presetId ?? ""),
          String(it.paletteId ?? ""),
          it.title,
          it.subtitle,
          it.subtitle2,
          it.prompt,
          it.opacity,
          it.position,
          updatedAt
        );
      }
      await client.query(
        `insert into text_styles(uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at)
         values ${parts.join(",")}
         on conflict(uid) do update set
           name=excluded.name,
           preset_id=excluded.preset_id,
           palette_id=excluded.palette_id,
           title=excluded.title,
           subtitle=excluded.subtitle,
           subtitle2=excluded.subtitle2,
           prompt=excluded.prompt,
           opacity=excluded.opacity,
           position=excluded.position,
           updated_at=excluded.updated_at`,
        values
      );
    }
    await client.query("commit");
    return { ok: true, updatedAt };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end();
  }
}
async function seedBossPresets(cfg) {
  const client = await connect8(cfg);
  try {
    const updatedAt = nowIso3();
    await client.query("begin");
    const seededFlag = await client.query("select value from app_settings where key = 'seedBossPresetsDone' limit 1");
    const alreadySeeded = String(seededFlag.rows?.[0]?.value ?? "").trim() === "1";
    if (alreadySeeded) {
      await client.query("commit");
      return { ok: true };
    }
    const negativeDefault = "No text, no typography, no watermark, no logos, no letters, no numbers, no captions, no UI overlays, no signatures, no frames, no borders.";
    const promptRows = [
      {
        uid: "bg-001",
        name: "Cyberpunk Neon 01",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic sports car in cyberpunk city, neon lights, wet road reflections, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-002",
        name: "Cyberpunk Neon 02",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, hypercar with neon blue and pink accents, smoke and light trails, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-003",
        name: "Cyberpunk Neon 03",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon-lit muscle car, glowing rims, purple fog, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-004",
        name: "Cyberpunk Neon 04",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, aggressive supercar with neon underglow, rain reflections, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-005",
        name: "Cyberpunk Neon 05",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, luxury hypercar glowing with neon lines, futuristic skyline, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-006",
        name: "Cyberpunk Neon 06",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, sports car with electric lightning energy, neon glow, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-007",
        name: "Cyberpunk Neon 07",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic car surrounded by plasma energy, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-008",
        name: "Cyberpunk Neon 08",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, cyberpunk car with electricity flowing through body lines, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-009",
        name: "Cyberpunk Neon 09",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon hypercar with energy waves and sparks, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-010",
        name: "Cyberpunk Neon 10",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, car with glowing energy trails and motion blur, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-011",
        name: "Cyberpunk Neon 11",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, supercar drifting with fire sparks, neon glow, smoke, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-012",
        name: "Cyberpunk Neon 12",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon car surrounded by colored smoke, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-013",
        name: "Cyberpunk Neon 13",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, aggressive car with flames and neon accents, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-014",
        name: "Cyberpunk Neon 14",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic car emerging from smoke, trending on artstation, unreal engine render, octane render, cinematic color grading"
      },
      {
        uid: "bg-015",
        name: "Cyberpunk Neon 15",
        negativePrompt: negativeDefault,
        scene: "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon-lit car with fire embers and fog, trending on artstation, unreal engine render, octane render, cinematic color grading"
      }
    ];
    for (const p of promptRows) {
      await client.query(
        "insert into prompt_templates(uid, name, scene, negative_prompt, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do nothing",
        [p.uid, p.name, p.scene, p.negativePrompt, updatedAt]
      );
    }
    await client.query(
      "insert into app_settings(key, value, updated_at) values ($1,$2,$3) on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
      ["seedBossPresetsDone", "1", updatedAt]
    );
    const structures = [
      {
        uid: "struct-1776779966347",
        name: "Tech House",
        content: "[Intro: kick + hi-hat groove, DJ friendly]\n[Groove: bassline enters, simple rhythm]\n[Build: add percussion layers]\n[Drop: full groove, catchy bassline hook]\n[Break: remove drums, filtered elements]\n[Build: reintroduce rhythm]\n[Drop: same groove with variation]\n[Outro: strip back for mixing]"
      },
      {
        uid: "struct-1776779935308",
        name: "TikTok",
        content: "[Hook Drop: immediate catchy drop, no intro, strong bass and melody]\n[Short Verse: minimal beat, quick vocal line]\n[Build-Up: fast riser, clap/snare build]\n[Drop: same hook repeated, slightly enhanced]\n[Break: very short pause or filtered section]\n[Drop: loopable, addictive, high energy]\n[Outro: quick ending]"
      },
      {
        uid: "struct-1776779918455",
        name: "POP EDM",
        content: "[Intro: soft piano or guitar, emotional vibe]\n[Verse: female vocal, intimate, minimal beat]\n[Pre-Chorus: build tension, add drums slowly]\n[Chorus: melodic drop with vocal hook, catchy and emotional]\n[Verse: variation, slightly fuller]\n[Pre-Chorus: rising energy]\n[Chorus: bigger drop, layered synths]\n[Bridge: emotional breakdown, minimal instruments]\n[Final Chorus: full energy, anthemic feel]\n[Outro: fade out with vocal]"
      },
      {
        uid: "struct-1776779899066",
        name: "Festival Big Drop (Suno Prompt Structure)",
        content: "[Intro: atmospheric pads, distant vocal chop, slow build]\n[Build-Up: risers, snare roll, tension increasing]\n[Drop: heavy big room kick, simple catchy lead melody, high energy]\n[Break: stripped back, emotional pad, vocal phrase]\n[Build-Up: stronger riser, faster snare roll, crowd hype]\n[Drop: bigger version, layered leads, more energy]\n[Outro: fade with pads and effects]"
      },
      { uid: "struct-1776779831633", name: "Main", content: "[Verse 1]\n[Chorus]\n[Verse 2]\n[Chorus]\n[Bridge]\n[Chorus]" }
    ];
    for (const s of structures) {
      await client.query(
        "insert into song_structures(uid, name, content, updated_at) values ($1,$2,$3,$4) on conflict(uid) do nothing",
        [s.uid, s.name, s.content, updatedAt]
      );
    }
    const descriptions = [
      {
        uid: "desc-1776780144364",
        name: "Party EDM",
        content: "A fun, high-energy EDM track at 142 BPM with a playful and danceable groove. Bright synths, catchy melodies, and a punchy kick drive the track, while the drop focuses on a simple, infectious rhythm that makes people want to move instantly. Designed for parties, clubs, and viral dance moments."
      },
      {
        uid: "desc-1776780134746",
        name: "Cyberpunk Bass Track",
        content: "A futuristic EDM track at 142 BPM with a cyberpunk aesthetic. Featuring glitchy effects, robotic vocal textures, and a heavy, distorted bassline. The drop hits with sharp, syncopated rhythms and digital sound design, giving it a unique and edgy vibe that stands out and feels modern and experimental."
      },
      {
        uid: "desc-1776780118348",
        name: "Emtional Melodic Rave",
        content: "An emotional yet powerful EDM track at 142 BPM combining soft piano elements with uplifting synth chords. The track builds from a heartfelt atmosphere into a euphoric drop with rich harmonies and strong sidechain energy. It balances emotional storytelling with festival-ready intensity, creating a goosebumps-inducing experience."
      },
      {
        uid: "desc-1776780103602",
        name: "TikTok",
        content: "A catchy, upbeat EDM track at 142 BPM designed for instant virality. The song starts strong with a memorable hook and bouncy bassline, featuring a simple, addictive melody that loops perfectly for short-form content. Clean production, punchy drums, and a fun, energetic vibe make it ideal for dance trends and repeat listens."
      },
      {
        uid: "desc-1776780090251",
        name: "Dark Festival Anthem",
        content: "A high-energy festival EDM track at 142 BPM with a dark, aggressive atmosphere. The song builds tension with cinematic pads and haunting vocal chants before exploding into a massive drop with punchy kicks, distorted bass, and a simple but powerful lead melody. Designed for mainstage crowds, with intense energy and a hard-hitting, unforgettable drop that feels epic and slightly ominous."
      }
    ];
    for (const d of descriptions) {
      await client.query(
        "insert into song_descriptions(uid, name, content, updated_at) values ($1,$2,$3,$4) on conflict(uid) do nothing",
        [d.uid, d.name, d.content, updatedAt]
      );
    }
    await client.query("commit");
    return { ok: true };
  } catch (e) {
    await client.query("rollback").catch(() => void 0);
    throw e;
  } finally {
    await client.end();
  }
}
async function bootstrapContent(cfg) {
  const [promptTemplates, structures, descriptions, textStyles, carModels] = await Promise.all([
    listPromptTemplates(cfg),
    listSongStructures(cfg),
    listSongDescriptions(cfg),
    listTextStyles(cfg),
    listCarModels(cfg)
  ]);
  return { promptTemplates, structures, descriptions, textStyles, carModels };
}

// electron/imageSamples.ts
import path8 from "node:path";
import { promises as fs8 } from "node:fs";
var supportedExts = /* @__PURE__ */ new Set([".png", ".jpg", ".jpeg", ".webp"]);
function isSupportedImageFileName(fileName) {
  const ext = path8.extname(fileName).toLowerCase();
  return supportedExts.has(ext);
}
async function listImagesInFolder(folderPath) {
  const dirents = await fs8.readdir(folderPath, { withFileTypes: true });
  const items = [];
  for (const d of dirents) {
    if (!d.isFile()) continue;
    if (!isSupportedImageFileName(d.name)) continue;
    const filePath = path8.join(folderPath, d.name);
    const st = await fs8.stat(filePath);
    items.push({
      filePath,
      fileUrl: `mgsamples://file?path=${encodeURIComponent(filePath)}`,
      fileName: d.name,
      mtimeMs: st.mtimeMs
    });
  }
  items.sort((a, b) => a.fileName.localeCompare(b.fileName));
  return items;
}

// electron/suno/sunoPoller.ts
import { existsSync as existsSync2 } from "node:fs";
async function pollAndDownloadPendingSuno(opts) {
  const apiKey = String(opts.apiKey || "").trim();
  if (!apiKey) return { ok: false, message: "Suno API key is missing" };
  const outputDir = String(opts.outputDir || "").trim();
  if (!outputDir) return { ok: false, message: "Suno output directory is missing" };
  const limit = Math.max(1, Math.min(40, opts.maxTasksPerRun ?? 10));
  const tasks = await listPendingSunoTasks(opts.db, limit);
  if (!tasks.length) return { ok: true, checked: 0, downloaded: 0 };
  const batchIndexCache = /* @__PURE__ */ new Map();
  let downloaded = 0;
  for (const t of tasks) {
    const r = await sunoApiTryGetTracks(apiKey, t.taskId);
    const okUrl = r.audioUrls[0] ? String(r.audioUrls[0]) : null;
    const altUrl = r.audioUrls[1] ? String(r.audioUrls[1]) : null;
    await upsertSunoTask(opts.db, {
      requestHash: t.requestHash,
      songUid: t.songUid,
      batchId: t.batchId,
      model: t.model,
      title: t.title,
      style: t.style,
      instrumental: t.instrumental,
      taskId: t.taskId,
      status: String(r.status || ""),
      audioUrlOk: okUrl,
      audioUrlAlt: altUrl,
      outputDirOk: t.outputDirOk,
      outputDirAlt: t.outputDirAlt
    });
    let trackNo = typeof t.trackNo === "number" && Number.isFinite(t.trackNo) ? Math.floor(t.trackNo) : void 0;
    if (!trackNo && t.batchId && t.songUid) {
      const batchId = String(t.batchId || "").trim();
      const songUid = String(t.songUid || "").trim();
      if (batchId && songUid) {
        let idx = batchIndexCache.get(batchId);
        if (!idx) {
          const songs = await listSongsByBatchId(opts.db, batchId);
          idx = new Map(
            songs.map((s, i) => [
              s.id,
              typeof s.batchIndex === "number" && Number.isFinite(s.batchIndex) ? Math.floor(s.batchIndex) : i + 1
            ])
          );
          batchIndexCache.set(batchId, idx);
        }
        trackNo = idx.get(songUid);
      }
    }
    if (okUrl) {
      const targetDir = String(t.outputDirOk || outputDir).trim() || outputDir;
      const paths = buildSunoOutputPaths({ outputDir: targetDir, title: t.title, trackNo });
      if (!existsSync2(paths.ok)) {
        await downloadToFile(okUrl, paths.ok);
        downloaded += 1;
      }
    }
    if (altUrl) {
      const targetDir = String(t.outputDirAlt || t.outputDirOk || outputDir).trim() || outputDir;
      const paths = buildSunoOutputPaths({ outputDir: targetDir, title: t.title, trackNo });
      if (!existsSync2(paths.alt)) {
        await downloadToFile(altUrl, paths.alt);
        downloaded += 1;
      }
    }
  }
  if (downloaded > 0) {
    console.log("[sunoPoller] downloaded", { checked: tasks.length, downloaded });
  }
  return { ok: true, checked: tasks.length, downloaded };
}

// electron/suno/callbackServer.ts
import { createServer } from "node:http";
async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk2 of req) {
    const buf = Buffer.isBuffer(chunk2) ? chunk2 : Buffer.from(String(chunk2));
    size += buf.length;
    if (size > 2e6) throw new Error("payload too large");
    chunks.push(buf);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  if (!raw.trim()) return null;
  return JSON.parse(raw);
}
async function startSunoCallbackServer(opts) {
  const cbPath = opts.path ?? "/suno/callback";
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url || "", `http://${req.headers.host || "localhost"}`);
      if (req.method !== "POST" || url.pathname !== cbPath) {
        res.statusCode = 404;
        res.end("not found");
        return;
      }
      const payload = await readJson(req);
      await opts.onCallback(payload);
      res.statusCode = 200;
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ ok: true }));
    } catch (e) {
      res.statusCode = 400;
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ ok: false, message: e instanceof Error ? e.message : "bad request" }));
    }
  });
  await new Promise((resolve, reject) => {
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });
  const addr = server.address();
  const port = typeof addr === "object" && addr ? addr.port : 0;
  return {
    port,
    close: async () => {
      await new Promise((resolve) => server.close(() => resolve()));
    }
  };
}

// electron/ngrok/ngrokManager.ts
import { spawn as spawn2 } from "node:child_process";
function parseJsonLine(line) {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}
function createNgrokManager() {
  let proc = null;
  let publicUrl = null;
  let callbackUrl = null;
  let localPort = null;
  let lastError = null;
  const status = () => ({
    running: Boolean(proc && !proc.killed),
    publicUrl,
    callbackUrl,
    localPort,
    lastError
  });
  const stop = async () => {
    if (!proc) return status();
    const p = proc;
    proc = null;
    await new Promise((resolve) => {
      p.once("close", () => resolve());
      try {
        p.kill();
      } catch {
        resolve();
      }
    });
    publicUrl = null;
    callbackUrl = null;
    localPort = null;
    return status();
  };
  const start = async (opts) => {
    if (proc) return status();
    lastError = null;
    publicUrl = null;
    callbackUrl = null;
    localPort = opts.localPort;
    const ngrokPath = String(opts.ngrokPath || "ngrok").trim() || "ngrok";
    const callbackPath = String(opts.callbackPath || "/suno/callback").trim() || "/suno/callback";
    const webPort = 4040;
    const fetchPublicUrl = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:${webPort}/api/tunnels`);
        if (!res.ok) return null;
        const json = await res.json();
        const urls = (json.tunnels || []).map((t) => String(t.public_url || "").trim()).filter(Boolean);
        const https = urls.find((u) => u.startsWith("https://"));
        return https || urls[0] || null;
      } catch {
        return null;
      }
    };
    proc = spawn2(
      ngrokPath,
      ["http", String(opts.localPort), "--log=stdout", "--log-format=json", "--web-addr", `127.0.0.1:${webPort}`],
      { windowsHide: true }
    );
    proc.on("error", (e) => {
      lastError = e instanceof Error ? e.message : "failed to start ngrok";
    });
    let buf = "";
    const onChunk = (chunk2) => {
      buf += chunk2.toString("utf-8");
      let idx = buf.indexOf("\n");
      while (idx >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 1);
        idx = buf.indexOf("\n");
        if (!line) continue;
        const obj = parseJsonLine(line);
        if (!obj) continue;
        const msg = typeof obj.msg === "string" ? obj.msg : "";
        const url = typeof obj.url === "string" ? obj.url : "";
        const err = typeof obj.err === "string" ? obj.err : "";
        if (err) lastError = err;
        if (!publicUrl && url && /started tunnel/i.test(msg)) {
          publicUrl = url;
          callbackUrl = `${url}${callbackPath.startsWith("/") ? callbackPath : `/${callbackPath}`}`;
        }
      }
    };
    proc.stdout.on("data", onChunk);
    proc.stderr.on("data", onChunk);
    const started = Date.now();
    while (Date.now() - started < 12e3) {
      if (lastError) break;
      if (publicUrl) break;
      const fromApi = await fetchPublicUrl();
      if (fromApi) {
        publicUrl = fromApi;
        callbackUrl = `${fromApi}${callbackPath.startsWith("/") ? callbackPath : `/${callbackPath}`}`;
        break;
      }
      await new Promise((r) => setTimeout(r, 200));
    }
    return status();
  };
  return { status, start, stop };
}

// electron/ffmpegVideoMerge.ts
import { promises as fs9 } from "node:fs";
import path9 from "node:path";
import { spawn as spawn3 } from "node:child_process";
function nowStamp2() {
  const d = /* @__PURE__ */ new Date();
  const p = (n) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}
function isVideoFile(fileName) {
  const lower = fileName.toLowerCase();
  return lower.endsWith(".mp4");
}
function parseResolution2(res) {
  const [wRaw, hRaw] = res.split("x");
  const w = Number(wRaw);
  const h = Number(hRaw);
  if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) throw new Error("Invalid resolution");
  return { w: Math.floor(w), h: Math.floor(h) };
}
async function runFfmpeg(ffmpegPath, args) {
  await new Promise((resolve, reject) => {
    const child = spawn3(ffmpegPath, args, { windowsHide: true });
    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || `ffmpeg exited with code ${code ?? -1}`));
    });
  });
}
async function mergeVideosInDirectory(input) {
  const directory = path9.resolve(input.directory);
  const entries = await fs9.readdir(directory, { withFileTypes: true });
  const videos = entries.filter((e) => e.isFile()).map((e) => e.name).filter(isVideoFile);
  if (!videos.length) {
    return { ok: false, message: "No video files found", outputPath: null, videoCount: 0 };
  }
  const collator = new Intl.Collator(void 0, { numeric: true, sensitivity: "base" });
  videos.sort((a, b) => collator.compare(a, b));
  const outDir = path9.join(directory, "merged");
  await fs9.mkdir(outDir, { recursive: true });
  const listContent = videos.map((name) => path9.resolve(directory, name)).map((fullPath) => `file '${fullPath.replace(/'/g, "'\\''")}'`).join("\n");
  const listFilePath = path9.resolve(outDir, `concat_${nowStamp2()}.txt`);
  await fs9.writeFile(listFilePath, listContent, "utf-8");
  const stamp2 = nowStamp2();
  const outPath = path9.resolve(outDir, `merged_${stamp2}.mp4`);
  const { w, h } = parseResolution2(input.exportSettings.resolution);
  const fps = input.exportSettings.fps;
  const preset = input.exportSettings.preset;
  const crf = Math.max(10, Math.min(40, Math.floor(input.exportSettings.crf)));
  const audioBitrate = `${input.exportSettings.audioBitrateKbps}k`;
  const vf = `scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2,fps=${fps}`;
  await runFfmpeg(input.ffmpegPath, [
    "-hide_banner",
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    listFilePath,
    "-vf",
    vf,
    "-c:v",
    "libx264",
    "-preset",
    preset,
    "-crf",
    String(crf),
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    audioBitrate,
    "-movflags",
    "+faststart",
    outPath
  ]);
  return { ok: true, message: "Merged", outputPath: outPath, videoCount: videos.length };
}

// electron/videoRender.ts
import path10 from "node:path";
import { spawn as spawn4 } from "node:child_process";
import { ipcMain } from "electron";
async function runVideoRender(opts) {
  const pythonPath = String(opts.pythonPath || "").trim() || "python";
  const ffmpegPath = String(opts.ffmpegPath || "").trim();
  if (!ffmpegPath) return { ok: false, message: "FFmpeg path is not configured" };
  const mp3Path = String(opts.input.mp3Path || "").trim();
  const backgroundPath = String(opts.input.backgroundPath || "").trim();
  const outputDir = String(opts.input.outputDir || "").trim();
  const templatePath = String(opts.input.templatePath || "").trim();
  const templateJsonB64 = String(opts.input.templateJsonB64 || "").trim();
  const logoPath = String(opts.input.logoPath || "").trim();
  const fps = Math.max(1, Math.min(60, Math.floor(Number(opts.input.fps ?? 30) || 30)));
  const width = Math.max(64, Math.min(8192, Math.floor(Number(opts.input.width ?? 1920) || 1920)));
  const height = Math.max(64, Math.min(8192, Math.floor(Number(opts.input.height ?? 1080) || 1080)));
  const renderer = opts.input.renderer === "cpu" ? "cpu" : "gpu";
  const previewPngPath = String(opts.input.previewPngPath || "").trim();
  const previewFrame = Math.max(0, Math.floor(Number(opts.input.previewFrame ?? 150) || 150));
  if (!mp3Path) return { ok: false, message: "MP3 path is required" };
  if (!backgroundPath) return { ok: false, message: "Background image path is required" };
  if (!outputDir) return { ok: false, message: "Output directory is required" };
  const visualizerRoot = path10.join(opts.appPath, "visualizer");
  const resolvedTemplatePath = templatePath || path10.join(visualizerRoot, "templates", "default.json");
  const args = [
    "-m",
    "visualizer.main",
    mp3Path,
    resolvedTemplatePath,
    "--background",
    backgroundPath,
    "--outputDir",
    outputDir,
    "--ffmpeg",
    ffmpegPath,
    "--renderer",
    renderer,
    "--fps",
    String(fps),
    "--width",
    String(width),
    "--height",
    String(height)
  ];
  if (previewPngPath) {
    args.push("--previewPng");
    args.push(previewPngPath);
    args.push("--previewFrame");
    args.push(String(previewFrame));
  }
  if (templateJsonB64) {
    args.push("--templateB64");
    args.push(templateJsonB64);
  }
  if (logoPath) {
    args.push("--logo");
    args.push(logoPath);
  }
  const child = spawn4(pythonPath, args, {
    windowsHide: true,
    cwd: opts.appPath,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1"
    }
  });
  let stdoutBuf = "";
  let stderrBuf = "";
  let lastOutputPath = "";
  const flushLines = () => {
    while (true) {
      const idx = stdoutBuf.indexOf("\n");
      if (idx < 0) return;
      const line = stdoutBuf.slice(0, idx).trim();
      stdoutBuf = stdoutBuf.slice(idx + 1);
      if (!line) continue;
      if (!line.startsWith("MG_EVENT ")) {
        console.log(`[videoRender stdout]: ${line}`);
        continue;
      }
      const payload = line.slice("MG_EVENT ".length);
      try {
        const evt = JSON.parse(payload);
        if (evt.outputPath) lastOutputPath = String(evt.outputPath);
        if (evt.status === "failed") {
          console.error(`[videoRender] MG_EVENT failed: ${String(evt.message || "")}`);
        }
        opts.onEvent({
          runId: opts.runId,
          status: evt.status ?? "running",
          message: String(evt.message || ""),
          progress: typeof evt.progress === "number" ? evt.progress : void 0,
          frame: typeof evt.frame === "number" ? evt.frame : void 0,
          totalFrames: typeof evt.totalFrames === "number" ? evt.totalFrames : void 0,
          outputPath: evt.outputPath ? String(evt.outputPath) : void 0
        });
      } catch {
        continue;
      }
    }
  };
  child.stdout.on("data", (chunk2) => {
    stdoutBuf += String(chunk2 || "");
    flushLines();
  });
  child.stderr.on("data", (chunk2) => {
    const s = String(chunk2 || "");
    stderrBuf += s;
    console.error(`[videoRender stderr]: ${s}`);
  });
  let isKilled = false;
  const onStop = () => {
    isKilled = true;
    try {
      child.kill();
    } catch {
    }
  };
  ipcMain.once("mg:videoRender:stop", onStop);
  return await new Promise((resolve) => {
    const finish = (res) => {
      ipcMain.removeListener("mg:videoRender:stop", onStop);
      resolve(res);
    };
    child.on("error", (e) => {
      console.error("[videoRender] Failed to start python process:", e);
      finish({ ok: false, message: e instanceof Error ? e.message : "Failed to start python process" });
    });
    child.on("exit", (code) => {
      if (isKilled) return finish({ ok: false, message: "Export stopped by user." });
      console.log(`[videoRender] Python process exited with code ${code}`);
      if (code === 0 && lastOutputPath) return finish({ ok: true, outputPath: lastOutputPath });
      const err = String(stderrBuf || "").trim();
      if (err) {
        console.error(`[videoRender] Python stderr:
${err}`);
        return finish({ ok: false, message: err.split("\n").slice(-6).join("\n") });
      }
      finish({ ok: false, message: `Video render failed (exit code ${code ?? "unknown"})` });
    });
  });
}

// electron/webglVideoRender.ts
import path11 from "node:path";
import { spawn as spawn5 } from "node:child_process";
import { promises as fs10 } from "node:fs";
import { randomUUID as randomUUID3 } from "node:crypto";
import { BrowserWindow, app, ipcMain as ipcMain2 } from "electron";
var jobs = /* @__PURE__ */ new Map();
var readyResolvers = /* @__PURE__ */ new Map();
var registered = false;
function registerWebglExportIpc() {
  if (registered) return;
  registered = true;
  ipcMain2.handle("mg:webglExport:getJob", async (_evt, input) => {
    const jobId = String(input?.jobId || "").trim();
    const job = jobs.get(jobId);
    if (!job) return { ok: false, message: "WebGL export job not found" };
    return { ok: true, job };
  });
  ipcMain2.on("mg:webglExport:ready", (_evt, payload) => {
    const jobId = String(payload?.jobId || "").trim();
    const r = readyResolvers.get(jobId);
    if (!r) return;
    readyResolvers.delete(jobId);
    r({ jobId, duration: Number(payload?.duration || 0) });
  });
}
async function runWebglVideoRender(input) {
  registerWebglExportIpc();
  const w = Math.max(64, Math.min(8192, Math.floor(Number(input.width) || 1920)));
  const h = Math.max(64, Math.min(8192, Math.floor(Number(input.height) || 1080)));
  const fps = Math.max(1, Math.min(60, Math.floor(Number(input.fps) || 30)));
  await fs10.mkdir(input.outputDir, { recursive: true });
  const outPath = path11.join(input.outputDir, input.outputName);
  const jobId = randomUUID3();
  const job = {
    jobId,
    mp3Path: input.mp3Path,
    backgroundPath: input.backgroundPath,
    logoPath: input.logoPath,
    template: input.template,
    width: w,
    height: h,
    fps
  };
  jobs.set(jobId, job);
  const win = new BrowserWindow({
    width: w,
    height: h,
    show: false,
    useContentSize: true,
    backgroundColor: "#000000",
    webPreferences: {
      preload: input.preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      offscreen: true
    }
  });
  try {
    if (input.devServerUrl) {
      await win.loadURL(`${input.devServerUrl}?webglExportJobId=${encodeURIComponent(jobId)}`);
    } else {
      const indexHtmlPath = path11.join(app.getAppPath(), "dist", "index.html");
      await win.loadFile(indexHtmlPath, { query: { webglExportJobId: jobId } });
    }
    const ready = await new Promise((resolve, reject) => {
      const t = setTimeout(() => {
        readyResolvers.delete(jobId);
        reject(new Error("WebGL export runner timed out"));
      }, 2e4);
      readyResolvers.set(jobId, (p) => {
        clearTimeout(t);
        resolve(p);
      });
    });
    const duration = Math.max(0, Number(ready.duration) || 0);
    if (!Number.isFinite(duration) || duration <= 0) return { ok: false, message: "Invalid audio duration for WebGL export" };
    const totalFrames = Math.max(1, Math.ceil(duration * fps));
    const preset = input.exportSettings.preset;
    const crf = Math.max(10, Math.min(40, Math.floor(input.exportSettings.crf)));
    const audioBitrate = `${input.exportSettings.audioBitrateKbps}k`;
    const ffmpegArgs = [
      "-hide_banner",
      "-y",
      "-f",
      "rawvideo",
      "-pix_fmt",
      "bgra",
      "-s",
      `${w}x${h}`,
      "-r",
      String(fps),
      "-i",
      "-",
      "-i",
      input.mp3Path,
      "-c:v",
      "libx264",
      "-preset",
      preset,
      "-crf",
      String(crf),
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      audioBitrate,
      "-shortest",
      "-movflags",
      "+faststart",
      outPath
    ];
    const ff = spawn5(input.ffmpegPath, ffmpegArgs, { windowsHide: true });
    let ffErr = "";
    ff.stderr.on("data", (d) => {
      ffErr += String(d || "");
    });
    const sleep2 = (ms) => new Promise((r) => setTimeout(r, ms));
    const waitDrain = () => new Promise((resolve, reject) => {
      ff.stdin.once("drain", () => resolve());
      ff.stdin.once("error", (e) => reject(e));
    });
    const startTs = Date.now();
    for (let frame = 0; frame < totalFrames; frame += 1) {
      if (input.shouldCancel()) {
        try {
          ff.kill();
        } catch {
        }
        return { ok: false, message: "Export stopped by user." };
      }
      const targetMs = Math.round(frame / fps * 1e3);
      const nowMs = Date.now() - startTs;
      const waitMs = targetMs - nowMs;
      if (waitMs > 0) await sleep2(waitMs);
      const image = await win.webContents.capturePage();
      const bmp = image.toBitmap();
      if (bmp.length !== w * h * 4) {
        try {
          ff.kill();
        } catch {
        }
        return { ok: false, message: `WebGL frame size mismatch (${bmp.length} bytes)` };
      }
      if (!ff.stdin.write(bmp)) await waitDrain();
      const progress = frame / totalFrames;
      input.onEvent({
        runId: input.runId,
        status: "running",
        message: `Rendering ${frame + 1}/${totalFrames}`,
        progress,
        frame: frame + 1,
        totalFrames,
        outputPath: outPath
      });
    }
    ff.stdin.end();
    const exitCode = await new Promise((resolve, reject) => {
      ff.on("error", reject);
      ff.on("close", (code) => resolve(code ?? -1));
    });
    if (exitCode !== 0) return { ok: false, message: String(ffErr || `ffmpeg exited with code ${exitCode}`).trim() };
    input.onEvent({ runId: input.runId, status: "done", message: "Done", progress: 1, outputPath: outPath });
    return { ok: true, outputPath: outPath };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : "WebGL export failed" };
  } finally {
    jobs.delete(jobId);
    try {
      win.destroy();
    } catch {
    }
  }
}

// electron/visualizerEnv.ts
import path12 from "node:path";
import crypto from "node:crypto";
import { promises as fs11 } from "node:fs";
import { spawn as spawn6 } from "node:child_process";
var isWindows = process.platform === "win32";
function venvPythonPath(venvDir) {
  return isWindows ? path12.join(venvDir, "Scripts", "python.exe") : path12.join(venvDir, "bin", "python");
}
function sha256Text(input) {
  return crypto.createHash("sha256").update(input, "utf-8").digest("hex");
}
async function runCmd(cmd, args, cwd) {
  return await new Promise((resolve) => {
    const child = spawn6(cmd, args, { cwd, windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
    let stderr = "";
    child.stderr.on("data", (c) => {
      stderr += String(c || "");
    });
    child.on("error", (e) => resolve({ ok: false, message: e instanceof Error ? e.message : "Failed to start process" }));
    child.on("close", (code) => {
      if (code === 0) return resolve({ ok: true });
      const tail = String(stderr || "").trim().split("\n").slice(-10).join("\n");
      resolve({ ok: false, message: tail || `Command failed (exit code ${code ?? "unknown"})` });
    });
  });
}
async function ensureVisualizerEnv(opts) {
  const basePythonPath = String(opts.basePythonPath || "").trim();
  if (!basePythonPath) return { ok: false, message: "Python executable was not found. Set Python path in Video tab." };
  const requirementsPath = path12.join(opts.appPath, "visualizer", "requirements.txt");
  if (!await pathExists(requirementsPath)) return { ok: false, message: "visualizer/requirements.txt was not found" };
  const requirementsText = await fs11.readFile(requirementsPath, "utf-8");
  const requirementsSha = sha256Text(requirementsText);
  const venvDir = path12.join(opts.userDataPath, "python", "visualizer");
  const pythonPath = venvPythonPath(venvDir);
  const markerPath = path12.join(venvDir, ".mg_env.json");
  const markerRaw = await pathExists(markerPath) ? await fs11.readFile(markerPath, "utf-8") : "";
  const marker = markerRaw ? JSON.parse(markerRaw) : null;
  const isReady = await pathExists(pythonPath) && marker?.requirementsSha === requirementsSha;
  if (isReady) return { ok: true, pythonPath };
  opts.onStatus?.("Preparing Python environment...");
  await fs11.mkdir(venvDir, { recursive: true });
  if (!await pathExists(pythonPath)) {
    opts.onStatus?.("Creating Python venv...");
    const r = await runCmd(basePythonPath, ["-m", "venv", venvDir], opts.appPath);
    if (r.ok === false) return { ok: false, message: `Failed to create venv: ${r.message}` };
  }
  opts.onStatus?.("Installing visualizer dependencies (first run only)...");
  const pipArgs = ["-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-r", requirementsPath];
  const install = await runCmd(pythonPath, pipArgs, opts.appPath);
  if (install.ok === false) return { ok: false, message: install.message };
  await fs11.writeFile(markerPath, JSON.stringify({ requirementsSha, installedAt: (/* @__PURE__ */ new Date()).toISOString() }, null, 2), "utf-8");
  return { ok: true, pythonPath };
}

// electron/main.ts
var __filename = fileURLToPath(import.meta.url);
var __dirname = path13.dirname(__filename);
var ngrok = createNgrokManager();
var callbackServer = null;
try {
  app2.setName("MusicGenerator");
  app2.setAppUserModelId("MusicGenerator");
} catch {
}
protocol.registerSchemesAsPrivileged([
  {
    scheme: "mgsamples",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true
    }
  }
]);
try {
  app2.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
} catch {
}
function createWindow() {
  const preloadPath = path13.join(__dirname, "preload.cjs");
  if (!existsSync3(preloadPath)) {
    throw new Error(`Preload not found at ${preloadPath}`);
  }
  const contentWidth = 1670;
  const contentHeight = 1080;
  const win = new BrowserWindow2({
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
      sandbox: false
    }
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
    const indexHtmlPath = path13.join(app2.getAppPath(), "dist", "index.html");
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
app2.whenReady().then(() => {
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
  const userDataDir = app2.getPath("userData");
  const debugLogPath = path13.join(userDataDir, "mg-debug.log");
  const sanitizeLogLine = (s) => {
    return String(s || "").replace(/Bearer\s+[A-Za-z0-9._-]+/g, "Bearer <redacted>").replace(/("password"\s*:\s*)"[^"]*"/gi, '$1"<redacted>"').replace(/(DEEPSEEK_API_KEY=)[^\s]+/gi, "$1<redacted>").replace(/(OPENAI_API_KEY=)[^\s]+/gi, "$1<redacted>").replace(/(SLAI(_IMG|_SONG)?_API_KEY=)[^\s]+/gi, "$1<redacted>");
  };
  const writeLogLine = (line) => {
    const stamped = `[${(/* @__PURE__ */ new Date()).toISOString()}] ${sanitizeLogLine(line)}
`;
    void fs12.appendFile(debugLogPath, stamped).catch(() => void 0);
  };
  const consoleLog = console.log.bind(console);
  const consoleWarn = console.warn.bind(console);
  const consoleError = console.error.bind(console);
  console.log = (...args) => {
    consoleLog(...args);
    writeLogLine(format(...args));
  };
  console.warn = (...args) => {
    consoleWarn(...args);
    writeLogLine(`WARN ${format(...args)}`);
  };
  console.error = (...args) => {
    consoleError(...args);
    writeLogLine(`ERROR ${format(...args)}`);
  };
  console.log("[debug] log file", debugLogPath);
  const dbConfigPath = getDbConfigPath({ isPackaged: app2.isPackaged, appPath: app2.getAppPath(), execPath: process.execPath });
  const APP_DATA_KEY = "app_data_v1";
  const queue = new JobQueue();
  const migratedDbKeys = /* @__PURE__ */ new Set();
  const sunoRunDirsByBatchId = /* @__PURE__ */ new Map();
  const injectDbSettings = (settings, cfg) => {
    return { ...settings, dbHost: cfg.host, dbPort: cfg.port, dbUser: cfg.user, dbPassword: cfg.password, dbName: cfg.database };
  };
  const stripDbConnectionSettings = (settings) => {
    return { ...settings, dbHost: "", dbPort: 5432, dbUser: "", dbPassword: "", dbName: "" };
  };
  async function readDbCfgOrNull() {
    return await readDbConfig(dbConfigPath);
  }
  async function requireDbCfg() {
    const cfg = await readDbCfgOrNull();
    if (!cfg) throw new Error(`Database is not configured. Create ${path13.basename(dbConfigPath)} in the app folder or set it in Settings \u2192 Database.`);
    return cfg;
  }
  async function readAppDataFromDb(cfg) {
    const base = createDefaultData();
    const stored = await getAppJson(cfg, APP_DATA_KEY);
    const profiles = await listProfiles(cfg);
    const merged = {
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
        ...stored?.settings ?? {}
      }
    };
    if (!merged.songDrafts?.length) merged.songDrafts = base.songDrafts;
    merged.settings = injectDbSettings(merged.settings, cfg);
    return merged;
  }
  async function writeAppDataToDb(cfg, data) {
    await syncProfiles(
      cfg,
      (data.profiles ?? []).map((p) => ({
        id: p.id,
        name: p.name,
        folderName: p.folderName,
        runPrefix: p.runPrefix,
        logoPath: p.logoPath
      }))
    );
    const toStore = {
      ...data,
      profiles: [],
      descriptions: [],
      structures: [],
      carModels: [],
      promptTemplates: [],
      textStyles: [],
      settings: stripDbConnectionSettings(data.settings)
    };
    await setAppJson(cfg, APP_DATA_KEY, toStore);
  }
  let sunoPollTimer = null;
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
    tick().catch(() => void 0);
    sunoPollTimer = setInterval(() => {
      tick().catch(() => void 0);
    }, 3e4);
  }
  function cleanupSunoRunDirs() {
    const cutoff = Date.now() - 6 * 60 * 60 * 1e3;
    for (const [k, v] of sunoRunDirsByBatchId) {
      if (v.createdAtMs < cutoff) sunoRunDirsByBatchId.delete(k);
    }
  }
  async function ensureMigrated(cfg) {
    const key = `${cfg.user}@${cfg.host}:${cfg.port}/${cfg.database}`;
    if (migratedDbKeys.has(key)) return;
    const res = await ensureDatabaseAndMigrate(cfg);
    if (res.ok) migratedDbKeys.add(key);
    else throw new Error(res.message);
    try {
      await seedBossPresets(cfg);
    } catch {
    }
  }
  function sanitizeFolderSegment(input) {
    return String(input || "").toLowerCase().replace(/[^a-z0-9 _.-]+/g, "").replace(/\s+/g, " ").trim().replace(/\s/g, "-").slice(0, 48);
  }
  async function planNextRunDir(baseDir, profileFolderName, prefix) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const profileFolder = sanitizeFolderSegment(profileFolderName) || "profile";
    const profileDir = path13.join(base, profileFolder);
    await fs12.mkdir(profileDir, { recursive: true });
    let entries = [];
    try {
      const listed = await fs12.readdir(profileDir, { withFileTypes: true });
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
    for (let n = maxN + 1; n < maxN + 1e4; n += 1) {
      const suffix = String(n).padStart(2, "0");
      const runFolderName = cleanPrefix ? `${cleanPrefix}_${suffix}` : suffix;
      const runDir = path13.join(profileDir, runFolderName);
      try {
        await fs12.mkdir(runDir, { recursive: false });
        return runDir;
      } catch {
        continue;
      }
    }
    throw new Error("Failed to allocate a new run folder");
  }
  function sanitizeRunLabel(input) {
    return String(input || "").replace(/[^a-zA-Z0-9 _.-]+/g, "").replace(/\s+/g, " ").trim().replace(/\s/g, "-").slice(0, 64);
  }
  function escapeRegex(input) {
    return String(input || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
  async function planNextRunDirByLabel(baseDir, profileFolderName, label) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const profileFolder = sanitizeFolderSegment(profileFolderName) || "profile";
    const profileDir = path13.join(base, profileFolder);
    await fs12.mkdir(profileDir, { recursive: true });
    const baseName = sanitizeRunLabel(label) || "run";
    let entries = [];
    try {
      const listed = await fs12.readdir(profileDir, { withFileTypes: true });
      entries = listed.filter((d) => d.isDirectory()).map((d) => d.name);
    } catch {
      entries = [];
    }
    const exactExists = entries.includes(baseName);
    if (!exactExists) {
      const runDir = path13.join(profileDir, baseName);
      await fs12.mkdir(runDir, { recursive: false });
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
    for (let n = maxN + 1; n < maxN + 1e4; n += 1) {
      const suffix = String(n).padStart(2, "0");
      const runFolderName = `${baseName}_${suffix}`;
      const runDir = path13.join(profileDir, runFolderName);
      try {
        await fs12.mkdir(runDir, { recursive: false });
        return runDir;
      } catch {
        continue;
      }
    }
    throw new Error("Failed to allocate a new run folder");
  }
  async function planNextPairedRunDirsByLabel(baseDir, okProfileFolderName, altProfileFolderName, label) {
    const base = String(baseDir || "").trim();
    if (!base) throw new Error("Suno output directory is not configured");
    const okFolder = sanitizeFolderSegment(okProfileFolderName) || "profile";
    const altFolder = altProfileFolderName ? sanitizeFolderSegment(altProfileFolderName) || "profile" : okFolder;
    const okProfileDir = path13.join(base, okFolder);
    const altProfileDir = path13.join(base, altFolder);
    await fs12.mkdir(okProfileDir, { recursive: true });
    await fs12.mkdir(altProfileDir, { recursive: true });
    const baseName = sanitizeRunLabel(label) || "run";
    const readDirs = async (dir) => {
      try {
        const listed = await fs12.readdir(dir, { withFileTypes: true });
        return listed.filter((d) => d.isDirectory()).map((d) => d.name);
      } catch {
        return [];
      }
    };
    const [okEntries, altEntries] = await Promise.all([readDirs(okProfileDir), readDirs(altProfileDir)]);
    const re = new RegExp(`^${escapeRegex(baseName)}_(\\d{2,})$`);
    const getMaxIndex = (entries) => {
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
    const okRunDir = path13.join(okProfileDir, runFolderName);
    const altRunDir = path13.join(altProfileDir, runFolderName);
    await fs12.mkdir(okRunDir, { recursive: false });
    if (altRunDir !== okRunDir) await fs12.mkdir(altRunDir, { recursive: false });
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
      }
    });
  })().catch(() => void 0);
  ipcMain3.on("mg:preload:ready", (_evt, payload) => {
    console.log("[preload] ready", payload);
  });
  queue.onEvent((event) => {
    win.webContents.send("mg:jobEvent", event);
  });
  ipcMain3.handle("mg:getData", async () => {
    const userDataDir2 = app2.getPath("userData");
    const dataFilePath = getDataFilePath(userDataDir2);
    let localData = null;
    try {
      localData = await readAppData(dataFilePath);
    } catch {
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
        settings: { ...base.settings, dbHost: "", dbPort: 5432, dbUser: "", dbPassword: "", dbName: "" }
      };
    }
    await ensureMigrated(db);
    const dbData = await readAppDataFromDb(db);
    if (localData && localData.settings) {
      const mergedSettings = { ...dbData.settings };
      for (const [k, v] of Object.entries(localData.settings)) {
        const existing = mergedSettings[k];
        if (typeof existing === "undefined" || existing === null) {
          mergedSettings[k] = v;
        }
      }
      dbData.settings = mergedSettings;
    }
    return dbData;
  });
  ipcMain3.handle("mg:setData", async (_evt, data) => {
    try {
      const userDataDir2 = app2.getPath("userData");
      const dataFilePath = getDataFilePath(userDataDir2);
      await writeAppData(dataFilePath, data);
    } catch {
    }
    const s = data.settings;
    const candidate = {
      host: s.dbHost,
      port: s.dbPort,
      user: s.dbUser,
      password: s.dbPassword,
      database: s.dbName
    };
    if (String(candidate.host || "").trim() && String(candidate.user || "").trim() && String(candidate.database || "").trim()) {
      await writeDbConfig(dbConfigPath, candidate);
    }
    const db = await readDbCfgOrNull();
    if (!db) return { ok: false, message: `Database is not configured. Create ${path13.basename(dbConfigPath)} in the app folder.` };
    await ensureMigrated(db);
    await writeAppDataToDb(db, data);
    return { ok: true };
  });
  ipcMain3.handle("mg:appendHistory", async (_evt, item) => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const data = await readAppDataFromDb(db);
      const next = {
        ...data,
        history: [item, ...data.history ?? []].slice(0, 2e3)
      };
      await writeAppDataToDb(db, next);
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Failed to append history" };
    }
  });
  ipcMain3.handle("mg:reset", async () => {
    const db = await requireDbCfg();
    await ensureMigrated(db);
    const base = createDefaultData();
    const next = {
      ...base,
      descriptions: [],
      structures: [],
      carModels: [],
      promptTemplates: [],
      textStyles: [],
      profiles: [],
      history: [],
      songs: []
    };
    await writeAppDataToDb(db, next);
    return await readAppDataFromDb(db);
  });
  ipcMain3.handle("mg:close", async () => {
    win.close();
    return { ok: true };
  });
  ipcMain3.handle("mg:queue:enqueue", async (_evt, payload) => {
    console.log("[queue:enqueue]", {
      jobType: payload.jobType,
      action: payload.jobType === "workflow" ? payload.action : void 0,
      batchId: payload.batchId
    });
    if (payload.jobType === "workflow" && payload.action === "generate" || payload.jobType === "suno") {
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
          throw new Error("No OK profile selected. Select a profile in Settings \u2192 Profiles.");
        }
        const batchKey = String(payload.batchId ?? "").trim();
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
          const out = runLabel ? await planNextPairedRunDirsByLabel(s.sunoOutputDir, okProfile.folderName, altProfile?.folderName ?? null, runLabel) : {
            okRunDir: await planNextRunDir(s.sunoOutputDir, okProfile.folderName, okProfile.runPrefix),
            altRunDir: altProfile ? await planNextRunDir(s.sunoOutputDir, altProfile.folderName, altProfile.runPrefix) : ""
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
          throw new Error("No OK profile selected. Select a profile in Settings \u2192 Profiles.");
        }
        const batchKey = String(payload.batchId ?? "").trim();
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
          const out = runLabel ? await planNextPairedRunDirsByLabel(s.sunoOutputDir, okProfile.folderName, altProfile?.folderName ?? null, runLabel) : {
            okRunDir: await planNextRunDir(s.sunoOutputDir, okProfile.folderName, okProfile.runPrefix),
            altRunDir: altProfile ? await planNextRunDir(s.sunoOutputDir, altProfile.folderName, altProfile.runPrefix) : ""
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
  ipcMain3.handle("mg:queue:cancel", async (_evt, jobId) => {
    return queue.cancel(jobId);
  });
  ipcMain3.handle("mg:ngrok:status", async () => {
    const s = ngrok.status();
    return { ...s, callbackPort: callbackServer?.port ?? null };
  });
  ipcMain3.handle("mg:ngrok:start", async (_evt, input) => {
    const port = callbackServer?.port;
    if (!port) return { ok: false, message: "Callback server is not ready" };
    const s = await ngrok.start({ ngrokPath: input?.ngrokPath, localPort: port, callbackPath: "/suno/callback" });
    return { ok: true, status: s };
  });
  ipcMain3.handle("mg:ngrok:stop", async () => {
    const s = await ngrok.stop();
    return { ok: true, status: s };
  });
  ipcMain3.handle("mg:queue:state", async () => {
    return queue.getState();
  });
  ipcMain3.handle("mg:openPath", async (_evt, targetPath) => {
    return await shell.openPath(targetPath);
  });
  ipcMain3.handle("mg:pathExists", async (_evt, targetPath) => {
    return { exists: await pathExists(targetPath) };
  });
  ipcMain3.handle("mg:showItemInFolder", async (_evt, targetPath) => {
    shell.showItemInFolder(targetPath);
    return { ok: true };
  });
  ipcMain3.handle("mg:suno:getSongOutputDirs", async (_evt, songUid) => {
    const db = await requireDbCfg();
    await ensureMigrated(db);
    const dirs = await getLatestSunoOutputDirsBySongUid(db, songUid);
    return { ok: true, ...dirs };
  });
  ipcMain3.handle("mg:suno:getBatchRunDirs", async (_evt, batchId) => {
    const key = String(batchId || "").trim();
    if (!key) return { ok: false, message: "Batch ID is empty" };
    cleanupSunoRunDirs();
    const existing = sunoRunDirsByBatchId.get(key) ?? null;
    return { ok: true, okDir: existing?.ok ?? null, altDir: existing?.alt ?? null };
  });
  ipcMain3.handle(
    "mg:pickPath",
    async (_evt, opts) => {
      const props = opts.kind === "directory" ? ["openDirectory"] : ["openFile"];
      const result = await dialog.showOpenDialog(win, {
        title: opts.title,
        defaultPath: opts.defaultPath,
        properties: [...props],
        filters: opts.filters
      });
      if (result.canceled) return { canceled: true };
      return { canceled: false, path: result.filePaths[0] ?? "" };
    }
  );
  ipcMain3.handle("mg:pickDirectories", async (_evt, opts) => {
    const result = await dialog.showOpenDialog(win, {
      title: opts?.title,
      defaultPath: opts?.defaultPath,
      properties: ["openDirectory", "multiSelections"]
    });
    if (result.canceled) return { canceled: true };
    const paths = (result.filePaths ?? []).filter((p) => typeof p === "string" && p.trim().length > 0);
    return { canceled: false, paths };
  });
  let videoMergeRunning = false;
  ipcMain3.handle(
    "mg:videoMerge:start",
    async (_evt, input) => {
      if (videoMergeRunning) return { ok: false, message: "Video merge is already running" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const data = await readAppDataFromDb(db);
      const s = data.settings;
      const ffmpegPath = String(s.ffmpegPath || "").trim();
      if (!ffmpegPath) return { ok: false, message: "FFmpeg path is not configured" };
      if (!await pathExists(ffmpegPath)) return { ok: false, message: "FFmpeg path does not exist" };
      const directories = Array.isArray(input.directories) ? input.directories.filter((d) => typeof d === "string" && d.trim().length > 0) : [];
      if (!directories.length) return { ok: false, message: "No directories selected" };
      const exportSettings = input.exportSettings;
      const runId = randomUUID4();
      videoMergeRunning = true;
      const total = directories.length;
      const send = (evt) => {
        try {
          win.webContents.send("mg:videoMergeEvent", evt);
        } catch {
          return;
        }
      };
      for (let i = 0; i < directories.length; i += 1) {
        send({ runId, index: i + 1, total, directory: directories[i], status: "pending", message: "Pending" });
      }
      setTimeout(async () => {
        try {
          for (let i = 0; i < directories.length; i += 1) {
            const dir = directories[i];
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
                  outputPath: r.outputPath ?? void 0
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
      return { ok: true, runId };
    }
  );
  let videoRenderRunning = false;
  let previewWorker = null;
  let visualizerEnvCache = null;
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
  const ensureVisualizerEnvCached = async (pythonPathUsed, projectRoot) => {
    const now = Date.now();
    if (visualizerEnvCache && now - visualizerEnvCache.atMs < 10 * 60 * 1e3 && visualizerEnvCache.pythonPath) {
      return { ok: true, pythonPath: visualizerEnvCache.pythonPath };
    }
    const env = await ensureVisualizerEnv({
      basePythonPath: pythonPathUsed,
      appPath: projectRoot,
      userDataPath: app2.getPath("userData"),
      onStatus: () => void 0
    });
    if (env.ok === false) return env;
    visualizerEnvCache = { pythonPath: env.pythonPath, atMs: now };
    return { ok: true, pythonPath: env.pythonPath };
  };
  const ensurePreviewWorker = async (pythonPathUsed, projectRoot) => {
    if (previewWorker) return { ok: true };
    const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
    if (env.ok === false) return env;
    const scriptPath = path13.join(projectRoot, "visualizer", "preview_worker.py");
    if (!existsSync3(scriptPath)) return { ok: false, message: "preview_worker.py not found" };
    const child = spawn7(env.pythonPath, ["-u", "-m", "visualizer.preview_worker"], {
      windowsHide: true,
      cwd: projectRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" }
    });
    const w = { child, buf: "", pending: /* @__PURE__ */ new Map() };
    previewWorker = w;
    child.stderr?.on("data", (chunk2) => {
      const s = String(chunk2 || "").trim();
      if (s) console.error(`[previewWorker stderr]: ${s}`);
    });
    child.stdout.on("data", (chunk2) => {
      const s = String(chunk2 || "");
      w.buf += s;
      for (; ; ) {
        const idx = w.buf.indexOf("\n");
        if (idx < 0) break;
        const line = w.buf.slice(0, idx).trim();
        w.buf = w.buf.slice(idx + 1);
        if (!line) continue;
        let msg = null;
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
    return { ok: true };
  };
  const renderPreviewWithWorker = async (input) => {
    const ready = await ensurePreviewWorker(input.pythonPathUsed, input.projectRoot);
    if (ready.ok === false) return ready;
    const w = previewWorker;
    if (!w) return { ok: false, message: "Preview worker is not running" };
    const id = randomUUID4();
    const timeoutMs = 2e4;
    const r = await new Promise((resolve, reject) => {
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
          outPngPath: input.outPngPath
        };
        w.child.stdin.write(`${JSON.stringify(payload)}
`);
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
  let livePreviewWorker = null;
  const stopLivePreviewWorker = () => {
    if (!livePreviewWorker) return;
    try {
      livePreviewWorker.child.kill();
    } catch {
    }
    livePreviewWorker = null;
  };
  ipcMain3.handle("mg:videoRender:startLivePreview", async (_evt, input) => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      let data = await readAppDataFromDb(db);
      let s = data.settings;
      const probeCmd = async (cmd, args2) => {
        return await new Promise((resolve) => {
          const child2 = spawn7(cmd, args2, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
          let stdout = "";
          const timer = setTimeout(() => {
            try {
              child2.kill();
            } catch {
            }
            resolve({ ok: false });
          }, 3e3);
          child2.stdout.on("data", (c) => {
            stdout += String(c || "");
          });
          child2.on("error", () => {
            clearTimeout(timer);
            resolve({ ok: false });
          });
          child2.on("close", (code) => {
            clearTimeout(timer);
            if (code === 0) return resolve({ ok: true, stdout: String(stdout || "") });
            resolve({ ok: false });
          });
        });
      };
      const detectPython = async (candidate) => {
        const cmd = String(candidate || "").trim();
        if (!cmd) return null;
        const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
        if (r.ok === false) return null;
        const resolved = String(r.stdout || "").trim();
        if (resolved && existsSync3(resolved)) return resolved;
        return cmd;
      };
      const pythonPathStored = String(s.pythonPath || "").trim();
      const pythonPathUsed = await detectPython(pythonPathStored) ?? await detectPython("py") ?? await detectPython("python") ?? await detectPython("python3") ?? "";
      if (!pythonPathUsed) return { ok: false, message: "Python executable not found." };
      const appPath = app2.getAppPath();
      const projectRoot = existsSync3(path13.join(appPath, "package.json")) ? appPath : process.cwd();
      const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
      if (env.ok === false) return env;
      stopLivePreviewWorker();
      const mp3PathRaw = String(input?.mp3Path || "").trim();
      const mp3Path = mp3PathRaw && await pathExists(mp3PathRaw) ? mp3PathRaw : "synthetic";
      const backgroundPathRaw = String(input?.backgroundPath || "").trim();
      const backgroundPath = backgroundPathRaw && await pathExists(backgroundPathRaw) ? backgroundPathRaw : "";
      const logoPath = String(input?.logoPath || "").trim();
      const templateJsonB64 = Buffer.from(JSON.stringify(input.template ?? {}), "utf-8").toString("base64");
      const w = 1280;
      const h = 720;
      const args = [
        "-u",
        "-m",
        "visualizer.main",
        mp3Path,
        "dummy.json",
        "--background",
        backgroundPath,
        "--logo",
        logoPath,
        "--templateB64",
        templateJsonB64,
        "--width",
        String(w),
        "--height",
        String(h),
        "--fps",
        "60",
        "--livePreview"
      ];
      const child = spawn7(env.pythonPath, args, {
        windowsHide: false,
        cwd: projectRoot,
        env: { ...process.env, PYTHONUNBUFFERED: "1" }
      });
      livePreviewWorker = { child, buf: "" };
      child.stderr?.on("data", (chunk2) => {
        const s2 = String(chunk2 || "").trim();
        if (s2) console.error(`[livePreview stderr]: ${s2}`);
      });
      child.stdout.on("data", (chunk2) => {
        const s2 = String(chunk2 || "");
        if (!livePreviewWorker) return;
        livePreviewWorker.buf += s2;
        for (; ; ) {
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
  ipcMain3.handle("mg:videoRender:updateLivePreview", async (_evt, input) => {
    if (!livePreviewWorker) return { ok: false, message: "Live preview is not running" };
    try {
      const payload = {};
      if (typeof input.time === "number") payload.time = input.time;
      if (input.template) payload.templateB64 = Buffer.from(JSON.stringify(input.template), "utf-8").toString("base64");
      if (typeof input.backgroundPath === "string") payload.backgroundPath = input.backgroundPath;
      if (typeof input.logoPath === "string") payload.logoPath = input.logoPath;
      if (typeof input.audioPath === "string") payload.audioPath = input.audioPath;
      livePreviewWorker.child.stdin.write(`${JSON.stringify(payload)}
`);
      return { ok: true };
    } catch (e) {
      return { ok: false, message: "Failed to send update" };
    }
  });
  ipcMain3.handle("mg:videoRender:stopLivePreview", async () => {
    stopLivePreviewWorker();
    return { ok: true };
  });
  ipcMain3.handle("mg:videoRender:start", async (_evt, input) => {
    if (videoRenderRunning) return { ok: false, message: "Video render is already running" };
    const db = await requireDbCfg();
    await ensureMigrated(db);
    let data = await readAppDataFromDb(db);
    let s = data.settings;
    const probeCmd = async (cmd, args) => {
      return await new Promise((resolve) => {
        const child = spawn7(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
        let stdout = "";
        const timer = setTimeout(() => {
          try {
            child.kill();
          } catch {
          }
          resolve({ ok: false });
        }, 3e3);
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
    const detectFfmpeg = async (candidate) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      if (existsSync3(cmd)) return cmd;
      const r = await probeCmd(cmd, ["-version"]);
      if (r.ok === false) return null;
      return cmd;
    };
    const ffmpegPathStored = String(s.ffmpegPath || "").trim();
    const ffmpegPathUsed = await detectFfmpeg(ffmpegPathStored) ?? await detectFfmpeg("ffmpeg") ?? await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe") ?? await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe") ?? "";
    if (!ffmpegPathUsed) return { ok: false, message: "FFmpeg was not found. Set FFmpeg path in Settings \u2192 Paths." };
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
    if (!mp3Path) return { ok: false, message: "MP3 path is required" };
    if (!backgroundPath) return { ok: false, message: "Background image path is required" };
    if (!outputDir) return { ok: false, message: "Output directory is required" };
    if (!await pathExists(mp3Path)) return { ok: false, message: "MP3 file does not exist" };
    if (!await pathExists(backgroundPath)) return { ok: false, message: "Background file does not exist" };
    if (logoPath && !await pathExists(logoPath)) return { ok: false, message: "Logo file does not exist" };
    const detectPython = async (candidate) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
      if (r.ok === false) return null;
      const resolved = String(r.stdout || "").trim();
      if (resolved && existsSync3(resolved)) return resolved;
      return cmd;
    };
    const pythonPathStored = String(s.pythonPath || "").trim();
    const pythonPathUsed = await detectPython(pythonPathStored) ?? await detectPython("py") ?? await detectPython("python") ?? await detectPython("python3") ?? "";
    if (!pythonPathUsed) return { ok: false, message: "Python executable was not found. Set Python path in Settings \u2192 Paths." };
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
      } else if (templateId.toLowerCase().endsWith(".json") && await pathExists(templateId)) {
        const raw = await fs12.readFile(templateId, "utf-8");
        const parsed = JSON.parse(raw);
        templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
      } else {
        return { ok: false, message: "Template not found" };
      }
    }
    try {
      await fs12.mkdir(outputDir, { recursive: true });
    } catch {
      return { ok: false, message: "Could not create output directory" };
    }
    const runId = randomUUID4();
    videoRenderRunning = true;
    const send = (evt) => {
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
        const appPath = app2.getAppPath();
        const projectRoot = existsSync3(path13.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnv({
          basePythonPath: pythonPathUsed,
          appPath: projectRoot,
          userDataPath: app2.getPath("userData"),
          onStatus: (message) => send({ runId, status: "running", message, progress: 0 })
        });
        if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });
        const parseRes = (r2) => {
          const s2 = String(r2 || "").trim();
          const m = s2.match(/^(\d+)x(\d+)$/);
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
            templateJsonB64: templateJsonB64 || void 0,
            logoPath: logoPath || void 0,
            fps: s.videoExport?.fps ?? 30,
            width: res.w,
            height: res.h,
            renderer: "gpu"
          },
          runId,
          onEvent: (evt) => send(evt)
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
    return { ok: true, runId };
  });
  let videoRenderCancelFlag = false;
  ipcMain3.handle("mg:videoRender:stop", async () => {
    videoRenderCancelFlag = true;
    ipcMain3.emit("mg:videoRender:stop");
    return { ok: true };
  });
  ipcMain3.handle("mg:listMp3s", async (_evt, dirPath) => {
    try {
      const files = await fs12.readdir(dirPath, { withFileTypes: true });
      const mp3Files = files.filter((f) => f.isFile() && f.name.toLowerCase().endsWith(".mp3")).map((f) => ({ path: path13.join(dirPath, f.name), name: f.name }));
      return { ok: true, files: mp3Files };
    } catch {
      return { ok: false, files: [] };
    }
  });
  ipcMain3.handle(
    "mg:videoRender:startBatch",
    async (_evt, input) => {
      if (videoRenderRunning) return { ok: false, message: "Video render is already running" };
      videoRenderCancelFlag = false;
      const mp3DirPath = String(input.mp3DirPath || "").trim();
      if (!mp3DirPath || !existsSync3(mp3DirPath)) return { ok: false, message: "Valid MP3 directory is required" };
      let mp3Files = [];
      try {
        const files = await fs12.readdir(mp3DirPath, { withFileTypes: true });
        mp3Files = files.filter((f) => f.isFile() && f.name.toLowerCase().endsWith(".mp3")).map((f) => path13.join(mp3DirPath, f.name));
      } catch {
        return { ok: false, message: "Failed to read MP3 directory" };
      }
      if (mp3Files.length === 0) return { ok: false, message: "No MP3 files found in directory" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      let data = await readAppDataFromDb(db);
      let s = data.settings;
      const probeCmd = async (cmd, args) => {
        return await new Promise((resolve) => {
          const child = spawn7(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
          let stdout = "";
          const timer = setTimeout(() => {
            try {
              child.kill();
            } catch {
            }
            resolve({ ok: false });
          }, 3e3);
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
      const detectFfmpeg = async (candidate) => {
        const cmd = String(candidate || "").trim();
        if (!cmd) return null;
        if (existsSync3(cmd)) return cmd;
        const r = await probeCmd(cmd, ["-version"]);
        if (r.ok === false) return null;
        return cmd;
      };
      const ffmpegPathStored = String(s.ffmpegPath || "").trim();
      const ffmpegPathUsed = await detectFfmpeg(ffmpegPathStored) ?? await detectFfmpeg("ffmpeg") ?? "";
      if (!ffmpegPathUsed) return { ok: false, message: "FFmpeg was not found. Set FFmpeg path in Settings \u2192 Paths." };
      const backgroundPath = String(input.backgroundPath || "").trim();
      const outputDir = String(input.outputDir || "").trim();
      const logoPath = String(input.logoPath || "").trim();
      if (!backgroundPath) return { ok: false, message: "Background image path is required" };
      if (!outputDir) return { ok: false, message: "Output directory is required" };
      if (!await pathExists(backgroundPath)) return { ok: false, message: "Background file does not exist" };
      if (logoPath && !await pathExists(logoPath)) return { ok: false, message: "Logo file does not exist" };
      const detectPython = async (candidate) => {
        const cmd = String(candidate || "").trim();
        if (!cmd) return null;
        const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
        if (r.ok === false) return null;
        const resolved = String(r.stdout || "").trim();
        if (resolved && existsSync3(resolved)) return resolved;
        return cmd;
      };
      const pythonPathStored = String(s.pythonPath || "").trim();
      const pythonPathUsed = await detectPython(pythonPathStored) ?? await detectPython("python") ?? "";
      if (!pythonPathUsed) return { ok: false, message: "Python executable was not found. Set Python path in Settings \u2192 Paths." };
      let templateJsonB64 = "";
      try {
        templateJsonB64 = Buffer.from(JSON.stringify(input.template || {}), "utf-8").toString("base64");
      } catch {
        return { ok: false, message: "Invalid template data" };
      }
      try {
        await fs12.mkdir(outputDir, { recursive: true });
      } catch {
        return { ok: false, message: "Could not create output directory" };
      }
      const runId = randomUUID4();
      videoRenderRunning = true;
      const send = (evt) => {
        try {
          win.webContents.send("mg:videoRenderEvent", evt);
        } catch {
        }
      };
      send({ runId, status: "pending", message: `Queued ${mp3Files.length} files for batch export`, progress: 0 });
      setTimeout(async () => {
        try {
          const appPath = app2.getAppPath();
          const projectRoot = existsSync3(path13.join(appPath, "package.json")) ? appPath : process.cwd();
          send({ runId, status: "running", message: "Preparing environment...", progress: 0 });
          const env = await ensureVisualizerEnv({
            basePythonPath: pythonPathUsed,
            appPath: projectRoot,
            userDataPath: app2.getPath("userData"),
            onStatus: (message) => send({ runId, status: "running", message, progress: 0 })
          });
          if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });
          const parseRes = (r) => {
            const s2 = String(r || "").trim();
            const m = s2.match(/^(\d+)x(\d+)$/);
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
            const fileName = path13.basename(mp3Path);
            const fileStartTs = Date.now();
            send({ runId, status: "running", message: `[${i + 1}/${mp3Files.length}] Rendering ${fileName}...`, progress: i / mp3Files.length });
            const onEvent = (evt) => {
              const frame = typeof evt.frame === "number" ? evt.frame : null;
              const totalFrames = typeof evt.totalFrames === "number" ? evt.totalFrames : null;
              let eta = "";
              if (frame && totalFrames && frame > 0 && totalFrames > 0) {
                const elapsedSec = (Date.now() - fileStartTs) / 1e3;
                const secPerFrame = elapsedSec / frame;
                const remainSec = Math.max(0, (totalFrames - frame) * secPerFrame);
                const mm = Math.floor(remainSec / 60);
                const ss = Math.floor(remainSec % 60);
                eta = ` ETA ${mm}:${String(ss).padStart(2, "0")}`;
              }
              send({ ...evt, message: `[${i + 1}/${mp3Files.length}] ${evt.message}${eta}` });
            };
            const r = engine === "webgl" ? await runWebglVideoRender({
              ffmpegPath: ffmpegPathUsed,
              exportSettings: s.videoExport,
              preloadPath: path13.join(__dirname, "preload.cjs"),
              devServerUrl: process.env.VITE_DEV_SERVER_URL,
              mp3Path,
              backgroundPath,
              outputDir,
              outputName: `${path13.basename(mp3Path, path13.extname(mp3Path))}.mp4`,
              logoPath: logoPath || void 0,
              template: input.template || {},
              width: res.w,
              height: res.h,
              fps: s.videoExport?.fps ?? 30,
              runId,
              onEvent,
              shouldCancel: () => videoRenderCancelFlag
            }) : await runVideoRender({
              pythonPath: env.pythonPath,
              ffmpegPath: ffmpegPathUsed,
              appPath: projectRoot,
              input: {
                mp3Path,
                backgroundPath,
                outputDir,
                templateJsonB64,
                logoPath: logoPath || void 0,
                fps: s.videoExport?.fps ?? 30,
                width: res.w,
                height: res.h,
                renderer: "gpu"
              },
              runId,
              onEvent
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
      return { ok: true, runId };
    }
  );
  ipcMain3.handle(
    "mg:videoRender:previewPng",
    async (_evt, input) => {
      if (videoRenderRunning) return { ok: false, message: "Video render is already running" };
      try {
        const db = await requireDbCfg();
        await ensureMigrated(db);
        let data = await readAppDataFromDb(db);
        let s = data.settings;
        const probeCmd = async (cmd, args) => {
          return await new Promise((resolve) => {
            const child = spawn7(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
            let stdout = "";
            const timer = setTimeout(() => {
              try {
                child.kill();
              } catch {
              }
              resolve({ ok: false });
            }, 3e3);
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
        const detectFfmpeg = async (candidate) => {
          const cmd = String(candidate || "").trim();
          if (!cmd) return null;
          if (existsSync3(cmd)) return cmd;
          const r = await probeCmd(cmd, ["-version"]);
          if (r.ok === false) return null;
          return cmd;
        };
        const ffmpegPathStored = String(s.ffmpegPath || "").trim();
        const ffmpegPathUsed = await detectFfmpeg(ffmpegPathStored) ?? await detectFfmpeg("ffmpeg") ?? await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe") ?? await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe") ?? "";
        if (!ffmpegPathUsed) return { ok: false, message: "FFmpeg was not found. Set FFmpeg path in Settings \u2192 Paths." };
        if (ffmpegPathStored !== ffmpegPathUsed) {
          try {
            data = { ...data, settings: { ...data.settings, ffmpegPath: ffmpegPathUsed } };
            s = data.settings;
            await writeAppDataToDb(db, data);
          } catch {
          }
        }
        const detectPython = async (candidate) => {
          const cmd = String(candidate || "").trim();
          if (!cmd) return null;
          const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
          if (r.ok === false) return null;
          const resolved = String(r.stdout || "").trim();
          if (resolved && existsSync3(resolved)) return resolved;
          return cmd;
        };
        const pythonPathStored = String(s.pythonPath || "").trim();
        const pythonPathUsed = await detectPython(pythonPathStored) ?? await detectPython("py") ?? await detectPython("python") ?? await detectPython("python3") ?? "";
        if (!pythonPathUsed) return { ok: false, message: "Python executable was not found. Set Python path in Settings \u2192 Paths." };
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
        const backgroundPath = backgroundPathRaw && await pathExists(backgroundPathRaw) ? backgroundPathRaw : "";
        if (backgroundPathRaw && !backgroundPath) return { ok: false, message: "Background file does not exist" };
        const mp3Path = mp3PathRaw && await pathExists(mp3PathRaw) ? mp3PathRaw : "synthetic";
        const templateInline = input.template;
        const templateId = String(input?.templatePath || s.videoRenderTemplatePath || "").trim();
        let templateJsonB64 = "";
        if (typeof templateInline !== "undefined") {
          templateJsonB64 = Buffer.from(JSON.stringify(templateInline ?? {}), "utf-8").toString("base64");
        } else if (templateId) {
          const tpl = await getVideoTemplate(db, templateId);
          if (tpl) {
            templateJsonB64 = Buffer.from(JSON.stringify(tpl.template ?? {}), "utf-8").toString("base64");
          } else if (templateId.toLowerCase().endsWith(".json") && await pathExists(templateId)) {
            const raw = await fs12.readFile(templateId, "utf-8");
            const parsed = JSON.parse(raw);
            templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
          } else {
            return { ok: false, message: "Template not found" };
          }
        }
        const previewDir = path13.join(app2.getPath("userData"), "video-previews");
        await fs12.mkdir(previewDir, { recursive: true });
        const outPath = path13.join(previewDir, `preview_${Date.now()}.png`);
        const fileUrl = `mgsamples://file?path=${encodeURIComponent(outPath)}`;
        const appPath = app2.getAppPath();
        const projectRoot = existsSync3(path13.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnvCached(pythonPathUsed, projectRoot);
        if (env.ok === false) return { ok: false, message: env.message };
        const parseRes = (r) => {
          const s2 = String(r || "").trim();
          const m = s2.match(/^(\d+)x(\d+)$/);
          const w2 = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h2 = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w: w2, h: h2 };
        };
        const baseRes = parseRes(s.videoExport?.resolution ?? "1920x1080");
        const w = Math.max(64, Math.min(1280, Math.floor(Number(input.width ?? 640) || 640)));
        const h = Math.max(64, Math.min(1280, Math.floor(Number(input.height ?? Math.round(w * baseRes.h / baseRes.w)) || 360)));
        const frame = Math.max(0, Math.floor(Number(input.frame ?? 8) || 8));
        const logoPath = String(input.logoPath || "").trim();
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
          outPngPath: outPath
        });
        if (rr.ok === false) {
          await stopPreviewWorker();
          if (String(rr.message || "").toLowerCase().includes("timeout")) {
            return { ok: false, message: rr.message };
          }
          const r2 = await runVideoRender({
            pythonPath: env.pythonPath,
            ffmpegPath: ffmpegPathUsed,
            appPath: projectRoot,
            input: {
              mp3Path,
              backgroundPath,
              outputDir: previewDir,
              templateJsonB64: templateJsonB64 || void 0,
              fps: s.videoExport?.fps ?? 30,
              width: w,
              height: h,
              renderer: "gpu",
              previewPngPath: outPath,
              previewFrame: frame,
              logoPath: logoPath || void 0
            },
            runId: randomUUID4(),
            onEvent: () => void 0
          });
          if (r2.ok !== true) return { ok: false, message: rr.message || r2.message };
        }
        return { ok: true, filePath: outPath, fileUrl };
      } catch (e) {
        return { ok: false, message: e instanceof Error ? e.message : "Preview failed" };
      }
    }
  );
  ipcMain3.handle("mg:videoRender:autoLatestBatch", async (_evt, input) => {
    if (videoRenderRunning) return { ok: false, message: "Video render is already running" };
    const db = await requireDbCfg();
    await ensureMigrated(db);
    let data = await readAppDataFromDb(db);
    let s = data.settings;
    const latest = await getLatestSunoBatchWithOutputDirs(db);
    if (!latest.ok) return { ok: false, message: latest.message };
    const okDir = String(latest.okDir || "").trim();
    const altDir = String(latest.altDir || "").trim();
    if (!okDir) return { ok: false, message: "No OK run directory found for latest batch" };
    const probeCmd = async (cmd, args) => {
      return await new Promise((resolve) => {
        const child = spawn7(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
        let stdout = "";
        const timer = setTimeout(() => {
          try {
            child.kill();
          } catch {
          }
          resolve({ ok: false });
        }, 3e3);
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
    const detectFfmpeg = async (candidate) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      if (existsSync3(cmd)) return cmd;
      const r = await probeCmd(cmd, ["-version"]);
      if (r.ok === false) return null;
      return cmd;
    };
    const ffmpegPathStored = String(s.ffmpegPath || "").trim();
    const ffmpegPathUsed = await detectFfmpeg(ffmpegPathStored) ?? await detectFfmpeg("ffmpeg") ?? await detectFfmpeg("C:\\ffmpeg\\bin\\ffmpeg.exe") ?? await detectFfmpeg("C:\\ffmpeg\\ffmpeg.exe") ?? "";
    if (!ffmpegPathUsed) return { ok: false, message: "FFmpeg was not found. Set FFmpeg path in Settings \u2192 Paths." };
    if (ffmpegPathStored !== ffmpegPathUsed) {
      try {
        data = { ...data, settings: { ...data.settings, ffmpegPath: ffmpegPathUsed } };
        s = data.settings;
        await writeAppDataToDb(db, data);
      } catch {
      }
    }
    const detectPython = async (candidate) => {
      const cmd = String(candidate || "").trim();
      if (!cmd) return null;
      const r = await probeCmd(cmd, ["-c", "import sys; print(sys.executable)"]);
      if (r.ok === false) return null;
      const resolved = String(r.stdout || "").trim();
      if (resolved && existsSync3(resolved)) return resolved;
      return cmd;
    };
    const pythonPathStored = String(s.pythonPath || "").trim();
    const pythonPathUsed = await detectPython(pythonPathStored) ?? await detectPython("py") ?? await detectPython("python") ?? await detectPython("python3") ?? "";
    if (!pythonPathUsed) return { ok: false, message: "Python executable was not found. Set Python path in Settings \u2192 Paths." };
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
      } else if (pickTemplateId.toLowerCase().endsWith(".json") && await pathExists(pickTemplateId)) {
        const raw = await fs12.readFile(pickTemplateId, "utf-8");
        const parsed = JSON.parse(raw);
        templateJsonB64 = Buffer.from(JSON.stringify(parsed), "utf-8").toString("base64");
      } else {
        return { ok: false, message: "Template not found" };
      }
    }
    const okBg = path13.join(okDir, "background.png");
    if (!await pathExists(okBg)) return { ok: false, message: "Batch background.png was not found in OK folder" };
    const okOut = path13.join(okDir, "video");
    const dirs = [];
    const okProfileId = s.activeProfileOkId ?? s.activeProfileId ?? null;
    const okLogo = okProfileId ? data.profiles.find((p) => p.id === okProfileId)?.logoPath ?? "" : "";
    dirs.push({ dir: okDir, background: okBg, outputDir: okOut, logoPath: okLogo || void 0 });
    if (altDir && altDir.toLowerCase() !== okDir.toLowerCase()) {
      const altBg = path13.join(altDir, "background.png");
      if (!await pathExists(altBg)) return { ok: false, message: "Batch background.png was not found in ALT folder" };
      const altOut = path13.join(altDir, "video");
      const altProfileId = s.activeProfileAltId ?? null;
      const altLogo = altProfileId ? data.profiles.find((p) => p.id === altProfileId)?.logoPath ?? "" : "";
      dirs.push({ dir: altDir, background: altBg, outputDir: altOut, logoPath: altLogo || void 0 });
    }
    const items = [];
    for (const d of dirs) {
      try {
        const listed = await fs12.readdir(d.dir, { withFileTypes: true });
        const mp3s = listed.filter((x) => x.isFile() && x.name.toLowerCase().endsWith(".mp3")).map((x) => path13.join(d.dir, x.name)).sort((a, b) => a.localeCompare(b));
        for (const mp3Path of mp3s) items.push({ mp3Path, backgroundPath: d.background, outputDir: d.outputDir, logoPath: d.logoPath });
      } catch {
        continue;
      }
    }
    if (!items.length) return { ok: false, message: "No MP3 files found in latest batch folders" };
    for (const it of items) {
      try {
        await fs12.mkdir(it.outputDir, { recursive: true });
      } catch {
        return { ok: false, message: "Could not create output directory" };
      }
    }
    const runId = randomUUID4();
    videoRenderRunning = true;
    const send = (evt) => {
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
        const appPath = app2.getAppPath();
        const projectRoot = existsSync3(path13.join(appPath, "package.json")) ? appPath : process.cwd();
        const env = await ensureVisualizerEnv({
          basePythonPath: pythonPathUsed,
          appPath: projectRoot,
          userDataPath: app2.getPath("userData"),
          onStatus: (message) => send({ runId, status: "running", message, progress: 0 })
        });
        if (env.ok === false) return send({ runId, status: "failed", message: env.message, progress: 0 });
        const parseRes = (r) => {
          const s2 = String(r || "").trim();
          const m = s2.match(/^(\d+)x(\d+)$/);
          const w = m ? Math.max(64, Math.min(8192, Number(m[1]))) : 1920;
          const h = m ? Math.max(64, Math.min(8192, Number(m[2]))) : 1080;
          return { w, h };
        };
        const res = parseRes(s.videoExport?.resolution ?? "1920x1080");
        const total = items.length;
        let lastOut = "";
        for (let i = 0; i < items.length; i += 1) {
          const cur = items[i];
          const label = path13.basename(cur.mp3Path);
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
              templateJsonB64: templateJsonB64 || void 0,
              logoPath: cur.logoPath || void 0,
              fps: s.videoExport?.fps ?? 30,
              width: res.w,
              height: res.h,
              renderer: "gpu"
            },
            runId,
            onEvent: (evt) => {
              const inner = typeof evt.progress === "number" ? Math.max(0, Math.min(1, evt.progress)) : 0;
              const combined = (i + inner) / total;
              if (evt.outputPath) lastOut = String(evt.outputPath);
              send({
                runId,
                status: evt.status,
                message: `(${i + 1}/${total}) ${label} \u2014 ${evt.message}`,
                progress: combined,
                frame: evt.frame,
                totalFrames: evt.totalFrames,
                outputPath: evt.outputPath
              });
            }
          });
          if (r.ok === true) lastOut = r.outputPath;
          else return send({ runId, status: "failed", message: r.message, progress: baseProgress });
        }
        send({ runId, status: "done", message: "Done", progress: 1, outputPath: lastOut || void 0 });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Video render failed";
        send({ runId, status: "failed", message: msg, progress: 0 });
      } finally {
        videoRenderRunning = false;
      }
    }, 0);
    return { ok: true, runId };
  });
  const normalizeVideoTemplateLabel = (input) => {
    return String(input || "").trim().replace(/[^a-zA-Z0-9 _.-]+/g, "").replace(/\s+/g, " ").slice(0, 64).trim();
  };
  ipcMain3.handle("mg:videoTemplates:list", async () => {
    try {
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const rows = await listVideoTemplates(db);
      const items = rows.map((r) => ({ label: r.name, path: r.id, source: r.source }));
      items.sort((a, b) => a.label.localeCompare(b.label));
      return { ok: true, items };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Template list failed" };
    }
  });
  ipcMain3.handle("mg:videoTemplates:read", async (_evt, input) => {
    try {
      const id = String(input?.path || "").trim();
      if (!id) return { ok: false, message: "Template ID is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const row = await getVideoTemplate(db, id);
      if (!row) return { ok: false, message: "Template not found" };
      return { ok: true, template: row.template };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Template read failed" };
    }
  });
  ipcMain3.handle("mg:videoTemplates:save", async (_evt, input) => {
    try {
      const label = normalizeVideoTemplateLabel(input?.label || "");
      if (!label) return { ok: false, message: "Template name is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const existing = (await listVideoTemplates(db)).find((t) => t.source === "user" && t.name.toLowerCase() === label.toLowerCase()) ?? null;
      const id = existing?.id ?? randomUUID4();
      await upsertVideoTemplate(db, { id, name: label, source: "user", template: input?.template ?? {} });
      return { ok: true, path: id };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Template save failed" };
    }
  });
  ipcMain3.handle("mg:videoTemplates:delete", async (_evt, input) => {
    try {
      const id = String(input?.path || "").trim();
      if (!id) return { ok: false, message: "Template ID is empty" };
      const db = await requireDbCfg();
      await ensureMigrated(db);
      const row = await getVideoTemplate(db, id);
      if (!row) return { ok: false, message: "Template not found" };
      if (row.source !== "user") return { ok: false, message: "Built-in templates cannot be deleted" };
      await deleteVideoTemplate(db, id);
      return { ok: true };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Template delete failed" };
    }
  });
  ipcMain3.handle("mg:imageSamples:list", async (_evt, input) => {
    const folderPath = String(input.folderPath || "").trim();
    if (!folderPath) return { ok: false, message: "No folder selected" };
    try {
      const items = await listImagesInFolder(folderPath);
      return { ok: true, items };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Could not read folder" };
    }
  });
  ipcMain3.handle("mg:content:bootstrap", async () => {
    const cfg = await requireDbCfg();
    await ensureMigrated(cfg);
    const res = await bootstrapContent(cfg);
    return { ok: true, ...res };
  });
  ipcMain3.handle(
    "mg:content:upsert",
    async (_evt, input) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      if (input.kind === "promptTemplates") return { ok: true, item: await upsertPromptTemplate(cfg, input.item) };
      if (input.kind === "structures") return { ok: true, item: await upsertSongStructure(cfg, input.item) };
      if (input.kind === "descriptions") return { ok: true, item: await upsertSongDescription(cfg, input.item) };
      if (input.kind === "textStyles") return { ok: true, item: await upsertTextStyle(cfg, input.item) };
      if (input.kind === "carModels") return { ok: true, item: await upsertCarModel(cfg, input.item) };
      return { ok: false, message: "Unknown kind" };
    }
  );
  ipcMain3.handle(
    "mg:content:delete",
    async (_evt, input) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      if (input.kind === "promptTemplates") return await deletePromptTemplate(cfg, input.id);
      if (input.kind === "structures") return await deleteSongStructure(cfg, input.id);
      if (input.kind === "descriptions") return await deleteSongDescription(cfg, input.id);
      if (input.kind === "textStyles") return await deleteTextStyle(cfg, input.id);
      if (input.kind === "carModels") return await deleteCarModel(cfg, input.id);
      return { ok: false, message: "Unknown kind" };
    }
  );
  ipcMain3.handle(
    "mg:content:bulkUpsertTextStyles",
    async (_evt, input) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      const res = await bulkUpsertTextStyles(cfg, input.items);
      return { ok: true, ...res };
    }
  );
  ipcMain3.handle(
    "mg:content:bulkUpsertCarModels",
    async (_evt, input) => {
      const cfg = await requireDbCfg();
      await ensureMigrated(cfg);
      const res = await bulkUpsertCarModels(cfg, input.items);
      return { ok: true, ...res };
    }
  );
  ipcMain3.handle(
    "mg:image:generateBackground",
    async (_evt, input) => {
      try {
        console.log("[image] generateBackground start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          sampleFile: path13.basename(String(input.sampleFilePath || "")),
          promptChars: String(input.prompt || "").length
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
          outputDir: input.outputDir
        });
        console.log("[image] generateBackground ok", { filePath: res.filePath, model });
        const outNameRaw = String(input.outputFileName || "").trim();
        if (outNameRaw) {
          const safeNameBase = path13.basename(outNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs12.mkdir(input.outputDir, { recursive: true });
          const finalPath = path13.join(input.outputDir, safeName);
          await fs12.copyFile(res.filePath, finalPath);
          const fileUrl2 = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          return { ok: true, filePath: finalPath, fileUrl: fileUrl2, meta: res.meta };
        }
        const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
        return { ok: true, filePath: res.filePath, fileUrl, meta: res.meta };
      } catch (e) {
        console.error("[image] generateBackground failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false, message: e instanceof Error ? e.message : "Image generation failed" };
      }
    }
  );
  ipcMain3.handle(
    "mg:image:generateBackgroundPrompt",
    async (_evt, input) => {
      try {
        return { ok: false, message: "Prompt-only background generation is disabled. Use sample-based background generation." };
      } catch (e) {
        return { ok: false, message: e instanceof Error ? e.message : "Image generation failed" };
      }
    }
  );
  ipcMain3.handle(
    "mg:image:generateThumbnail",
    async (_evt, input) => {
      try {
        console.log("[image] generateThumbnail start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          backgroundFile: path13.basename(String(input.backgroundFilePath || "")),
          promptChars: String(input.prompt || "").length
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
          outputDir: input.outputDir
        });
        console.log("[image] generateThumbnail ok", { filePath: res.filePath, model });
        const outNameRaw = String(input.outputFileName || "").trim();
        if (outNameRaw) {
          const safeNameBase = path13.basename(outNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs12.mkdir(input.outputDir, { recursive: true });
          const finalPath = path13.join(input.outputDir, safeName);
          await fs12.copyFile(res.filePath, finalPath);
          const fileUrl2 = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          return { ok: true, filePath: finalPath, fileUrl: fileUrl2, meta: res.meta };
        }
        const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
        return { ok: true, filePath: res.filePath, fileUrl, meta: res.meta };
      } catch (e) {
        console.error("[image] generateThumbnail failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false, message: e instanceof Error ? e.message : "Thumbnail generation failed" };
      }
    }
  );
  ipcMain3.handle(
    "mg:image:generateThumbnailBestOf",
    async (_evt, input) => {
      try {
        console.log("[image] generateThumbnailBestOf start", {
          resolution: input.resolution,
          outputDir: input.outputDir,
          backgroundFile: path13.basename(String(input.backgroundFilePath || "")),
          promptChars: String(input.prompt || "").length,
          count: input.count
        });
        const db = await requireDbCfg();
        await ensureMigrated(db);
        const data = await readAppDataFromDb(db);
        const apiKey = String(input.apiKey || data.settings.slaiImgApiKey || process.env.SLAI_IMG_API_KEY || "").trim();
        const model = String(data.settings.slaiImgModel || "cgpt-web/gpt-5.5-pro").trim();
        const count = Math.max(1, Math.min(8, Math.floor(Number(input.count ?? 4) || 4)));
        const candidates = [];
        for (let i = 0; i < count; i += 1) {
          const res = await generateThumbnailWithSlai({
            apiKey,
            model,
            prompt: input.prompt,
            backgroundFilePath: input.backgroundFilePath,
            resolution: input.resolution,
            outputDir: input.outputDir
          });
          const fileUrl = `mgsamples://file?path=${encodeURIComponent(res.filePath)}`;
          const score = scoreImageLumaStddev({ filePath: res.filePath });
          candidates.push({ filePath: res.filePath, fileUrl, score });
        }
        const best = candidates.reduce((a, b) => b.score > a.score ? b : a, candidates[0]);
        const finalNameRaw = String(input.finalFileName || "").trim();
        if (finalNameRaw) {
          const safeNameBase = path13.basename(finalNameRaw).replace(/[/\\]+/g, "");
          const safeName = safeNameBase.toLowerCase().endsWith(".png") ? safeNameBase : `${safeNameBase}.png`;
          await fs12.mkdir(input.outputDir, { recursive: true });
          const finalPath = path13.join(input.outputDir, safeName);
          await fs12.copyFile(best.filePath, finalPath);
          const finalUrl = `mgsamples://file?path=${encodeURIComponent(finalPath)}`;
          if (!input.keepCandidates) {
            await Promise.all(candidates.map((c) => fs12.unlink(c.filePath).catch(() => void 0)));
            return { ok: true, filePath: finalPath, fileUrl: finalUrl, candidates: [] };
          }
          return { ok: true, filePath: finalPath, fileUrl: finalUrl, candidates };
        }
        return { ok: true, filePath: best.filePath, fileUrl: best.fileUrl, candidates };
      } catch (e) {
        console.error("[image] generateThumbnailBestOf failed", e instanceof Error ? e.stack || e.message : e);
        return { ok: false, message: e instanceof Error ? e.message : "Thumbnail generation failed" };
      }
    }
  );
  ipcMain3.handle(
    "mg:image:listGenerated",
    async (_evt, input) => {
      try {
        const root = String(input.outputDir || "").trim();
        if (!root) return { ok: false, message: "Output directory is required" };
        const kind = input.kind === "thumbnail" ? "thumbnail" : "background";
        const limit = Math.max(1, Math.min(200, Math.floor(Number(input.limit ?? 50) || 50)));
        const items = [];
        const currentName = kind === "background" ? "background.png" : "thumbnail.png";
        const currentPath = path13.join(root, currentName);
        try {
          const st = await fs12.stat(currentPath);
          if (st.isFile()) {
            items.push({
              filePath: currentPath,
              fileUrl: `mgsamples://file?path=${encodeURIComponent(currentPath)}`,
              mtimeMs: st.mtimeMs
            });
          }
        } catch {
        }
        const dirName = kind === "background" ? "backgrounds" : "thumbnails";
        const dirPath = path13.join(root, dirName);
        let names = [];
        try {
          names = await fs12.readdir(dirPath);
        } catch {
          names = [];
        }
        const rows = [];
        for (const name of names) {
          if (!name.toLowerCase().endsWith(".png")) continue;
          const fp = path13.join(dirPath, name);
          try {
            const st = await fs12.stat(fp);
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
            mtimeMs: r.mtimeMs
          });
        }
        const seen = /* @__PURE__ */ new Set();
        const uniq = items.filter((x) => {
          if (seen.has(x.filePath)) return false;
          seen.add(x.filePath);
          return true;
        });
        uniq.sort((a, b) => b.mtimeMs - a.mtimeMs);
        return { ok: true, items: uniq.slice(0, limit) };
      } catch (e) {
        return { ok: false, message: e instanceof Error ? e.message : "Failed to list images" };
      }
    }
  );
  ipcMain3.handle(
    "mg:db:testConnection",
    async (_evt, cfg) => {
      return await testPostgresConnection({
        host: cfg.host,
        port: cfg.port,
        user: cfg.user,
        password: cfg.password,
        database: cfg.database,
        timeoutMs: 6e3
      });
    }
  );
  ipcMain3.handle(
    "mg:db:ensureAndMigrate",
    async (_evt, cfg) => {
      return await ensureDatabaseAndMigrate(cfg);
    }
  );
  ipcMain3.handle(
    "mg:pools:stats",
    async (_evt, cfg) => {
      await ensureMigrated(cfg);
      return await poolStats(cfg);
    }
  );
  ipcMain3.handle(
    "mg:pools:import",
    async (_evt, input) => {
      await ensureMigrated(input.cfg);
      const raw = await fs12.readFile(input.filePath, "utf-8");
      if (input.kind === "titles") {
        const lines2 = raw.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
        return await importTitles(input.cfg, lines2);
      }
      if (input.kind === "albums") {
        const lines2 = raw.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
        return await importAlbums(input.cfg, lines2);
      }
      const pairs = [];
      const lines = raw.split(/\r?\n/);
      for (const line of lines) {
        const t = line.trim();
        if (!t) continue;
        const sep = t.includes("	") ? "	" : t.includes("|") ? "|" : null;
        if (sep) {
          const [a, b] = t.split(sep).map((x) => x.trim());
          if (a && b) pairs.push({ line1: a, line2: b });
        } else {
          const last = pairs[pairs.length - 1];
          if (!last || last.line1 && last.line2) pairs.push({ line1: t, line2: "" });
          else last.line2 = t;
        }
      }
      return await importOpenings(input.cfg, pairs.filter((p) => p.line1 && p.line2));
    }
  );
  ipcMain3.handle(
    "mg:pools:list",
    async (_evt, input) => {
      await ensureMigrated(input.cfg);
      return await listPool(input.cfg, { kind: input.kind, limit: input.limit, offset: input.offset });
    }
  );
  ipcMain3.handle(
    "mg:pools:generate",
    async (_evt, input) => {
      await ensureMigrated(input.cfg);
      return await generateAndInsert(input.cfg, { kind: input.kind, count: input.count });
    }
  );
  ipcMain3.handle(
    "mg:pools:clear",
    async (_evt, input) => {
      await ensureMigrated(input.cfg);
      return await clearPool(input.cfg, input.kind);
    }
  );
  ipcMain3.handle(
    "mg:db:clearGenerated",
    async (_evt, cfg) => {
      await ensureMigrated(cfg);
      return await clearGenerated(cfg);
    }
  );
  ipcMain3.handle("mg:ffmpeg:download", async (_evt, opts) => {
    return await downloadFfmpeg(opts);
  });
  ipcMain3.handle("mg:lyrics:polish", async (_evt, input) => {
    const apiKey = input.apiKey || process.env.OPENAI_API_KEY;
    if (!apiKey) return { ok: false, message: "OpenAI API key is not configured" };
    try {
      const lyrics = await polishLyricsWithOpenAI({ apiKey, lyrics: input.lyrics, strength: input.strength });
      return { ok: true, lyrics };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : "Polish failed" };
    }
  });
  app2.on("activate", () => {
    if (BrowserWindow2.getAllWindows().length === 0) createWindow();
  });
});
app2.on("window-all-closed", () => {
  if (process.platform !== "darwin") app2.quit();
});
app2.on("before-quit", async () => {
  try {
    await ngrok.stop();
  } catch {
  }
  try {
    await callbackServer?.close();
  } catch {
  }
});
//# sourceMappingURL=main.js.map
