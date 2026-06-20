import { create } from "zustand";
import type {
  AppData,
  CarModel,
  HistoryItem,
  ImageSample,
  Profile,
  PromptTemplate,
  SavedText,
  Song,
  SongDraft,
  TextStyle,
} from "../../shared/app-types";
import { dataClient } from "@/services/dataClient";
import { createId, nowIso } from "@/utils/ids";

type AppStore = {
  hydrated: boolean;
  data: AppData;
  currentDescription: string;
  currentStructure: string;
  currentSongId: string | null;
  thumbnailUrl: string | null;
  running: boolean;
  footerText: string;
  footerProgress: number | null;
  hydrate: () => Promise<void>;
  persist: (data: AppData) => Promise<void>;
  setCurrentDescription: (v: string) => void;
  setCurrentStructure: (v: string) => void;
  setCurrentSongId: (v: string | null) => void;
  setThumbnailUrl: (v: string | null) => void;
  setRunning: (v: boolean) => void;
  setFooterStatus: (text: string, progress: number | null) => void;
  updateSettings: (patch: Partial<AppData["settings"]>) => Promise<void>;
  saveText: (kind: "descriptions" | "structures", nameHint: string | null, content: string) => Promise<void>;
  upsertText: (kind: "descriptions" | "structures", item: SavedText) => Promise<void>;
  deleteText: (kind: "descriptions" | "structures", id: string) => Promise<void>;
  addSong: (song: Omit<Song, "id" | "createdAt"> & Partial<Pick<Song, "id" | "createdAt">>) => Promise<Song>;
  updateSong: (id: string, patch: Partial<Song>) => Promise<void>;
  deleteSong: (id: string) => Promise<void>;
  clearSongs: () => Promise<void>;
  createProfile: (name: string) => Promise<void>;
  updateProfile: (id: string, patch: Partial<Profile>) => Promise<void>;
  deleteProfile: (id: string) => Promise<void>;
  setActiveProfileId: (id: string | null) => Promise<void>;
  updateSongDraft: (id: string, patch: Partial<SongDraft>) => Promise<void>;
  upsertCarModel: (item: CarModel) => Promise<void>;
  deleteCarModel: (id: string) => Promise<void>;
  seedCarModels: (count: number) => Promise<void>;
  upsertImageSample: (item: ImageSample) => Promise<void>;
  deleteImageSample: (id: string) => Promise<void>;
  upsertPromptTemplate: (item: PromptTemplate) => Promise<void>;
  deletePromptTemplate: (id: string) => Promise<void>;
  upsertTextStyle: (item: TextStyle) => Promise<void>;
  deleteTextStyle: (id: string) => Promise<void>;
  replaceTextStyles: (items: TextStyle[]) => Promise<void>;
  addHistory: (item: Omit<HistoryItem, "id" | "createdAt"> & { status?: HistoryItem["status"] }) => Promise<void>;
  resetAll: () => Promise<void>;
  refreshDbContent: () => Promise<void>;
};

const emptyData: AppData = {
  descriptions: [],
  structures: [],
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

function nextAutoName(items: SavedText[]) {
  const nums = items
    .map((x) => Number.parseInt(x.name, 10))
    .filter((n) => Number.isFinite(n));
  const next = (nums.length ? Math.max(...nums) + 1 : 1).toString().padStart(2, "0");
  return next;
}

function seedCarModels(count: number): CarModel[] {
  const makes = ["Toyota", "BMW", "Audi", "Tesla", "Honda", "Ford", "Nissan", "Mercedes", "Hyundai", "Kia"];
  const models = ["Supra", "M3", "A4", "Model 3", "Civic", "Mustang", "GTR", "C-Class", "Ioniq", "Stinger"];
  const trims = ["Base", "Sport", "Premium", "Limited", "Performance", "SE", "GT", "RS"];
  const cats = ["Coupe", "Sedan", "Hatch", "SUV", "Truck", "Wagon"];
  const updatedAt = nowIso();

  const out: CarModel[] = [];
  for (let i = 0; i < count; i++) {
    out.push({
      id: createId("car"),
      make: makes[i % makes.length],
      model: models[i % models.length],
      trim: trims[i % trims.length],
      year: 2012 + (i % 14),
      category: cats[i % cats.length],
      updatedAt,
    });
  }
  return out;
}

function hasDbConfigured(settings: AppData["settings"]) {
  return Boolean(settings.dbHost && settings.dbUser && settings.dbName);
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

function stripDbBackedData(data: AppData): AppData {
  return {
    ...data,
    descriptions: [],
    structures: [],
    carModels: [],
    promptTemplates: [],
    textStyles: [],
  };
}

export const useAppStore = create<AppStore>((set, get) => ({
  hydrated: false,
  data: emptyData,
  currentDescription: "",
  currentStructure: "",
  currentSongId: null,
  thumbnailUrl: null,
  running: false,
  footerText: "Ready",
  footerProgress: null,
  hydrate: async () => {
    const data = await dataClient.getData();
    const res = (data as Partial<AppData>).settings?.imageResolution;
    const imageResolution = res === "1080x1920" || res === "1920x1080" ? res : emptyData.settings.imageResolution;
    const songs = ((data as Partial<AppData>).songs ?? []).map((s) => ({
      ...s,
      batchId: s.batchId ?? "legacy",
      batchIndex: typeof (s as Partial<Song>).batchIndex === "number" ? (s as Partial<Song>).batchIndex : undefined,
      songDescription: (s as Partial<Song>).songDescription ?? "",
      songStructure: (s as Partial<Song>).songStructure ?? "",
      songDescriptionTitle: (s as Partial<Song>).songDescriptionTitle ?? "",
      songStructureTitle: (s as Partial<Song>).songStructureTitle ?? "",
      profileOkId: (s as Partial<Song>).profileOkId ?? "",
      profileAltId: (s as Partial<Song>).profileAltId ?? "",
      profileOkName: (s as Partial<Song>).profileOkName ?? "",
      profileAltName: (s as Partial<Song>).profileAltName ?? "",
    }));
    const songDrafts = (data as Partial<AppData>).songDrafts?.length
      ? (data as Partial<AppData>).songDrafts!
      : emptyData.songDrafts;
    const storedSettings = (data as Partial<AppData>).settings ?? emptyData.settings;
    const shuffleDescription = (storedSettings as Partial<AppData["settings"]>).shuffleDescription ?? false;
    const shuffleStructure = (storedSettings as Partial<AppData["settings"]>).shuffleStructure ?? false;
    const matchDescriptionStructure = (storedSettings as Partial<AppData["settings"]>).matchDescriptionStructure ?? false;
    const cycleStructures = (storedSettings as Partial<AppData["settings"]>).cycleStructures ?? false;
    const enabledDescriptionIds = (storedSettings as Partial<AppData["settings"]>).enabledDescriptionIds ?? [];
    const enabledStructureIds = (storedSettings as Partial<AppData["settings"]>).enabledStructureIds ?? [];
    const rawActiveDescriptionIds = (storedSettings as { activeDescriptionIds?: unknown }).activeDescriptionIds;
    const rawActiveStructureIds = (storedSettings as { activeStructureIds?: unknown }).activeStructureIds;
    const legacyActiveDescriptionId = (storedSettings as { activeDescriptionId?: unknown }).activeDescriptionId;
    const legacyActiveStructureId = (storedSettings as { activeStructureId?: unknown }).activeStructureId;

    let activeDescriptionIds = Array.isArray(rawActiveDescriptionIds)
      ? rawActiveDescriptionIds.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
      : [];
    let activeStructureIds = Array.isArray(rawActiveStructureIds)
      ? rawActiveStructureIds.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
      : [];

    if (!activeDescriptionIds.length && typeof legacyActiveDescriptionId === "string" && legacyActiveDescriptionId.trim().length > 0) {
      activeDescriptionIds = [legacyActiveDescriptionId];
    }
    if (!activeStructureIds.length && typeof legacyActiveStructureId === "string" && legacyActiveStructureId.trim().length > 0) {
      activeStructureIds = [legacyActiveStructureId];
    }
    const uniqueOpening = (storedSettings as Partial<AppData["settings"]>).uniqueOpening ?? false;
    const strictLevel = (storedSettings as Partial<AppData["settings"]>).strictLevel ?? 3;
    const uniquenessHistoryWindow = (storedSettings as Partial<AppData["settings"]>).uniquenessHistoryWindow ?? 100;
    const imageSamplesDir = (storedSettings as Partial<AppData["settings"]>).imageSamplesDir ?? "";
    const backgroundSourceModeRaw = (storedSettings as Partial<AppData["settings"]>).backgroundSourceMode;
    const backgroundSourceMode = backgroundSourceModeRaw === "prompt" ? "prompt" : "samples";
    const thumbnailOverlayMode = "ai";
    const autoGenSongs = (storedSettings as Partial<AppData["settings"]>).autoGenSongs ?? true;
    const autoGenImage = (storedSettings as Partial<AppData["settings"]>).autoGenImage ?? true;
    const autoGSuno = (storedSettings as Partial<AppData["settings"]>).autoGSuno ?? false;
    const sunoDefaultVersion = (storedSettings as Partial<AppData["settings"]>).sunoDefaultVersion ?? "v5.5";
    const sunoMergeEnabled = (storedSettings as Partial<AppData["settings"]>).sunoMergeEnabled ?? false;
    const sunoMergeGroupSize = (storedSettings as Partial<AppData["settings"]>).sunoMergeGroupSize ?? 5;
    const sunoApiKey = (storedSettings as Partial<AppData["settings"]>).sunoApiKey ?? "";
    const sunoOutputDir = (storedSettings as Partial<AppData["settings"]>).sunoOutputDir ?? "D:\\MusicGenerator\\downloads\\suno";
    const sunoCallbackUrl =
      (storedSettings as Partial<AppData["settings"]>).sunoCallbackUrl ?? "https://api.example.com/callback";
    const storedVideoExport = (storedSettings as Partial<AppData["settings"]>).videoExport;
    const videoExport =
      storedVideoExport && typeof storedVideoExport === "object"
        ? { ...emptyData.settings.videoExport, ...(storedVideoExport as AppData["settings"]["videoExport"]) }
        : emptyData.settings.videoExport;
    const rawVideoMergeDirectories = (storedSettings as Partial<AppData["settings"]>).videoMergeDirectories;
    const videoMergeDirectories = Array.isArray(rawVideoMergeDirectories)
      ? rawVideoMergeDirectories.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
      : emptyData.settings.videoMergeDirectories;

    const profilesRaw = (data as Partial<AppData>).profiles ?? [];
    const profiles: Profile[] = profilesRaw
      .filter(Boolean)
      .map((p) => {
        const id = String((p as Partial<Profile>).id || "").trim() || createId("prof");
        const name = String((p as Partial<Profile>).name || "Profile").trim() || "Profile";
        const folderName =
          String((p as Partial<Profile>).folderName || "").trim() || sanitizeFolderSegment(name) || `profile-${id.slice(-6)}`;
        const runPrefix = String((p as Partial<Profile>).runPrefix || "").trim();
        const logoPath = String((p as Partial<Profile>).logoPath || "").trim();
        const createdAt = String((p as Partial<Profile>).createdAt || nowIso());
        const updatedAt = String((p as Partial<Profile>).updatedAt || createdAt);
        return { id, name, folderName, runPrefix, logoPath, createdAt, updatedAt };
      });
    const storedActiveProfileId = (storedSettings as Partial<AppData["settings"]>).activeProfileId ?? null;
    const storedOkId = (storedSettings as Partial<AppData["settings"]>).activeProfileOkId ?? null;
    const storedAltId = (storedSettings as Partial<AppData["settings"]>).activeProfileAltId ?? null;
    const rawChannelOkIds = (storedSettings as Partial<AppData["settings"]>).channelOkProfileIds ?? [];
    const rawChannelAltIds = (storedSettings as Partial<AppData["settings"]>).channelAltProfileIds ?? [];

    const activeProfileOkId =
      (storedOkId && profiles.some((p) => p.id === storedOkId) ? storedOkId : null) ||
      (storedActiveProfileId && profiles.some((p) => p.id === storedActiveProfileId) ? storedActiveProfileId : null) ||
      profiles[0]?.id ||
      null;

    const activeProfileAltId = storedAltId && profiles.some((p) => p.id === storedAltId) ? storedAltId : null;
    const activeProfileId = activeProfileOkId;
    const channelOkProfileIds = Array.isArray(rawChannelOkIds)
      ? rawChannelOkIds.filter((id): id is string => typeof id === "string" && profiles.some((p) => p.id === id))
      : [];
    const channelAltProfileIds = Array.isArray(rawChannelAltIds)
      ? rawChannelAltIds.filter((id): id is string => typeof id === "string" && profiles.some((p) => p.id === id))
      : [];
    const finalChannelOkProfileIds = channelOkProfileIds.length ? channelOkProfileIds : activeProfileOkId ? [activeProfileOkId] : [];
    const finalChannelAltProfileIds = channelAltProfileIds.length ? channelAltProfileIds : activeProfileAltId ? [activeProfileAltId] : [];

    const rawTextStyles = (data as Partial<AppData>).textStyles ?? [];
    const textStyles = rawTextStyles.map((s) => {
      const baseSubtitle = (s as Partial<TextStyle>).subtitle ?? "";
      const baseSubtitle2 = (s as Partial<TextStyle>).subtitle2;
      const basePrompt = (s as Partial<TextStyle>).prompt;
      if (typeof baseSubtitle2 === "string") {
        return {
          ...s,
          subtitle: baseSubtitle,
          subtitle2: baseSubtitle2,
          prompt: typeof basePrompt === "string" ? basePrompt : "",
        } as TextStyle;
      }

      const parts = String(baseSubtitle)
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean);
      return {
        ...(s as TextStyle),
        subtitle: parts[0] ?? "",
        subtitle2: parts[1] ?? "",
        prompt: typeof basePrompt === "string" ? basePrompt : "",
      };
    });

    const descriptions = (data as Partial<AppData>).descriptions ?? [];
    const structures = (data as Partial<AppData>).structures ?? [];

    const dbConfigured = hasDbConfigured(storedSettings as AppData["settings"]);
    if (!dbConfigured || descriptions.length > 0) {
      activeDescriptionIds = activeDescriptionIds.filter((id) => descriptions.some((d) => d.id === id));
    }
    if (!dbConfigured || structures.length > 0) {
      activeStructureIds = activeStructureIds.filter((id) => structures.some((s) => s.id === id));
    }

    const normalized: AppData = {
      ...emptyData,
      ...data,
      songs,
      songDrafts,
      profiles,
      settings: {
        ...emptyData.settings,
        ...storedSettings,
        activeProfileId,
        activeProfileOkId,
        activeProfileAltId,
        channelOkProfileIds: finalChannelOkProfileIds,
        channelAltProfileIds: finalChannelAltProfileIds,
        imageResolution,
        shuffleDescription,
        shuffleStructure,
        matchDescriptionStructure,
        cycleStructures,
        activeDescriptionIds,
        activeStructureIds,
        enabledDescriptionIds,
        enabledStructureIds,
        uniqueOpening,
        strictLevel,
        uniquenessHistoryWindow,
        imageSamplesDir,
        backgroundSourceMode,
        thumbnailOverlayMode,
        autoGenSongs,
        autoGenImage,
        autoGSuno,
        sunoDefaultVersion,
        sunoMergeEnabled,
        sunoMergeGroupSize,
        sunoApiKey,
        sunoOutputDir,
        sunoCallbackUrl,
        videoExport,
        videoMergeDirectories,
      },
      history: (data as Partial<AppData>).history ?? [],
      descriptions,
      structures,
      carModels: (data as Partial<AppData>).carModels ?? [],
      imageSamples: (data as Partial<AppData>).imageSamples ?? [],
      promptTemplates: ((data as Partial<AppData>).promptTemplates ?? []).map((t) => {
        const r = t as unknown as Partial<{ id: string; name: string; scene: string; negativePrompt: string; content: string; tags: string[]; updatedAt: string }>;
        return {
          id: String(r.id ?? createId("tpl")),
          name: String(r.name ?? ""),
          scene: String(r.scene ?? r.content ?? ""),
          negativePrompt: String(r.negativePrompt ?? ""),
          updatedAt: String(r.updatedAt ?? nowIso()),
        };
      }),
      textStyles,
    };

    set({
      hydrated: true,
      data: normalized,
      currentDescription: normalized.descriptions[0]?.content ?? "",
      currentStructure: normalized.structures[0]?.content ?? "",
      currentSongId: normalized.songs[0]?.id ?? null,
    });

    if (typeof window !== "undefined" && window.mgApi?.contentBootstrap && hasDbConfigured(normalized.settings)) {
      try {
        const res = await window.mgApi.contentBootstrap();
        if (res.ok) {
          const next: AppData = {
            ...get().data,
            carModels: res.carModels,
            promptTemplates: res.promptTemplates.map((t) => ({
              id: t.id,
              name: t.name,
              scene: t.scene,
              negativePrompt: t.negativePrompt,
              updatedAt: t.updatedAt,
            })),
            structures: res.structures.map((s) => ({
              id: s.id,
              name: s.name,
              content: s.text,
              matchKey: s.matchKey ?? "",
              updatedAt: s.updatedAt,
            })),
            descriptions: res.descriptions.map((d) => ({
              id: d.id,
              name: d.name,
              content: d.text,
              matchKey: d.matchKey ?? "",
              updatedAt: d.updatedAt,
            })),
            textStyles: res.textStyles,
          };
          next.settings = {
            ...next.settings,
            activeDescriptionIds: (next.settings.activeDescriptionIds ?? []).filter((id) => next.descriptions.some((d) => d.id === id)),
            activeStructureIds: (next.settings.activeStructureIds ?? []).filter((id) => next.structures.some((s) => s.id === id)),
          };
          set({
            data: next,
            currentDescription: next.descriptions[0]?.content ?? get().currentDescription,
            currentStructure: next.structures[0]?.content ?? get().currentStructure,
          });
        }
      } catch {
        // ignore
      }
    }
  },
  persist: async (data) => {
    set({ data });

    const next = hasDbConfigured(data.settings) ? stripDbBackedData(data) : data;
    await dataClient.setData(next);
  },
  setCurrentDescription: (v) => set({ currentDescription: v }),
  setCurrentStructure: (v) => set({ currentStructure: v }),
  setCurrentSongId: (v) => set({ currentSongId: v }),
  setThumbnailUrl: (v) => set({ thumbnailUrl: v }),
  setRunning: (v) => set({ running: v }),
  setFooterStatus: (text, progress) => set({ footerText: text, footerProgress: progress }),
  updateSettings: async (patch) => {
    const { data } = get();
    const next = { ...data, settings: { ...data.settings, ...patch } };
    await get().persist(next);
  },
  saveText: async (kind, nameHint, content) => {
    const { data } = get();
    const updatedAt = nowIso();
    const name = nameHint && nameHint.trim() ? nameHint.trim() : nextAutoName(data[kind]);
    const id = createId(kind === "descriptions" ? "desc" : "struct");
    const item: SavedText = { id, name, content, matchKey: "", updatedAt };

    if (typeof window !== "undefined" && window.mgApi?.contentUpsert && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentUpsert({
        kind: kind === "descriptions" ? "descriptions" : "structures",
        item: { id: item.id, name: item.name, text: item.content, matchKey: item.matchKey ?? "" },
      });
      if (res?.ok) {
        const out: SavedText = {
          id: String(res.item.id),
          name: String(res.item.name ?? ""),
          content: String(res.item.text ?? ""),
          matchKey: String((res.item as { matchKey?: unknown }).matchKey ?? ""),
          updatedAt: String(res.item.updatedAt ?? updatedAt),
        };
        set({ data: { ...data, [kind]: [out, ...data[kind]] } });
      }
      return;
    }

    const next = { ...data, [kind]: [item, ...data[kind]] };
    await get().persist(next);
  },
  upsertText: async (kind, item) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItem: SavedText = {
      id: item.id,
      name: item.name,
      content: item.content,
      matchKey: item.matchKey ?? "",
      updatedAt,
    };

    if (typeof window !== "undefined" && window.mgApi?.contentUpsert && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentUpsert({
        kind: kind === "descriptions" ? "descriptions" : "structures",
        item: { id: nextItem.id, name: nextItem.name, text: nextItem.content, matchKey: nextItem.matchKey ?? "" },
      });
      if (res?.ok) {
        const out: SavedText = {
          id: String(res.item.id),
          name: String(res.item.name ?? ""),
          content: String(res.item.text ?? ""),
          matchKey: String((res.item as { matchKey?: unknown }).matchKey ?? ""),
          updatedAt: String(res.item.updatedAt ?? updatedAt),
        };
        const exists = data[kind].some((x) => x.id === out.id);
        const nextList = exists ? data[kind].map((x) => (x.id === out.id ? out : x)) : [out, ...data[kind]];
        set({ data: { ...data, [kind]: nextList } });
      }
      return;
    }

    const exists = data[kind].some((x) => x.id === item.id);
    const nextList = exists ? data[kind].map((x) => (x.id === item.id ? nextItem : x)) : [nextItem, ...data[kind]];
    const next = { ...data, [kind]: nextList };
    await get().persist(next);
  },
  deleteText: async (kind, id) => {
    const { data } = get();

    if (typeof window !== "undefined" && window.mgApi?.contentDelete && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentDelete({
        kind: kind === "descriptions" ? "descriptions" : "structures",
        id,
      });
      if (res?.ok) set({ data: { ...data, [kind]: data[kind].filter((x) => x.id !== id) } });
      return;
    }

    const next = { ...data, [kind]: data[kind].filter((x) => x.id !== id) };
    await get().persist(next);
  },
  addSong: async (song) => {
    const id = song.id ?? createId("song");
    const createdAt = song.createdAt ?? nowIso();
    const full: Song = {
      id,
      title: song.title,
      album: song.album,
      lyricsRaw: song.lyricsRaw,
      lyricsPolished: song.lyricsPolished,
      batchIndex: song.batchIndex,
      songDescriptionTitle: song.songDescriptionTitle ?? "",
      songStructureTitle: song.songStructureTitle ?? "",
      songDescription: song.songDescription,
      songStructure: song.songStructure,
      language: song.language,
      creativity: song.creativity,
      batchId: song.batchId,
      createdAt,
    };
    const { data } = get();
    const next = { ...data, songs: [full, ...data.songs] };
    await get().persist(next);
    set({ currentSongId: full.id });
    return full;
  },
  updateSong: async (id, patch) => {
    const { data } = get();
    const nextSongs = data.songs.map((s) => (s.id === id ? { ...s, ...patch } : s));
    const next = { ...data, songs: nextSongs };
    await get().persist(next);
  },
  deleteSong: async (id) => {
    const { data, currentSongId } = get();
    const nextSongs = data.songs.filter((s) => s.id !== id);
    const nextCurrent = currentSongId === id ? nextSongs[0]?.id ?? null : currentSongId;
    const next = { ...data, songs: nextSongs };
    await get().persist(next);
    set({ currentSongId: nextCurrent });
  },
  clearSongs: async () => {
    const { data } = get();
    const next = { ...data, songs: [] };
    await get().persist(next);
    set({ currentSongId: null });
  },
  createProfile: async (name) => {
    const displayName = String(name || "").trim();
    if (!displayName) return;

    const { data } = get();
    const baseFolder = sanitizeFolderSegment(displayName) || "profile";
    let folderName = baseFolder;
    let n = 2;
    while (data.profiles.some((p) => p.folderName === folderName)) {
      folderName = `${baseFolder}-${n}`;
      n += 1;
    }

    const createdAt = nowIso();
    const id = createId("prof");
    const profile: Profile = {
      id,
      name: displayName,
      folderName,
      runPrefix: "",
      logoPath: "",
      createdAt,
      updatedAt: createdAt,
    };

    const next: AppData = {
      ...data,
      profiles: [profile, ...data.profiles],
      settings: { ...data.settings, activeProfileId: id, activeProfileOkId: id },
    };
    await get().persist(next);
  },
  updateProfile: async (id, patch) => {
    const { data } = get();
    const nextProfiles = data.profiles.map((p) =>
      p.id === id
        ? {
            ...p,
            ...patch,
            name: String((patch as Partial<Profile>).name ?? p.name),
            folderName: String((patch as Partial<Profile>).folderName ?? p.folderName),
            runPrefix: String((patch as Partial<Profile>).runPrefix ?? p.runPrefix),
            updatedAt: nowIso(),
          }
        : p,
    );
    const next = { ...data, profiles: nextProfiles };
    await get().persist(next);
  },
  deleteProfile: async (id) => {
    const { data } = get();
    const nextProfiles = data.profiles.filter((p) => p.id !== id);
    const nextOk = data.settings.activeProfileOkId === id ? nextProfiles[0]?.id ?? null : data.settings.activeProfileOkId;
    const nextAlt = data.settings.activeProfileAltId === id ? null : data.settings.activeProfileAltId;
    const next = {
      ...data,
      profiles: nextProfiles,
      settings: { ...data.settings, activeProfileId: nextOk ?? null, activeProfileOkId: nextOk ?? null, activeProfileAltId: nextAlt },
    };

    await get().persist(next);
  },
  setActiveProfileId: async (id) => {
    await get().updateSettings({ activeProfileId: id, activeProfileOkId: id });
  },
  updateSongDraft: async (id, patch) => {
    const { data } = get();
    const nextDrafts = data.songDrafts.map((d) => (d.id === id ? { ...d, ...patch } : d));
    const next = { ...data, songDrafts: nextDrafts };
    await get().persist(next);
  },
  upsertCarModel: async (item) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItem = { ...item, updatedAt };

    if (typeof window !== "undefined" && window.mgApi?.contentUpsert && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentUpsert({ kind: "carModels", item: nextItem });
      if (res?.ok) {
        const out = { ...nextItem, ...res.item };
        const exists = data.carModels.some((x) => x.id === out.id);
        const nextList = exists ? data.carModels.map((x) => (x.id === out.id ? out : x)) : [out, ...data.carModels];
        set({ data: { ...data, carModels: nextList } });
      }
      return;
    }

    const exists = data.carModels.some((x) => x.id === item.id);
    const next = {
      ...data,
      carModels: exists ? data.carModels.map((x) => (x.id === item.id ? nextItem : x)) : [nextItem, ...data.carModels],
    };
    await get().persist(next);
  },
  deleteCarModel: async (id) => {
    const { data } = get();

    if (typeof window !== "undefined" && window.mgApi?.contentDelete && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentDelete({ kind: "carModels", id });
      if (res?.ok) set({ data: { ...data, carModels: data.carModels.filter((x) => x.id !== id) } });
      return;
    }

    const next = { ...data, carModels: data.carModels.filter((x) => x.id !== id) };
    await get().persist(next);
  },
  seedCarModels: async (count) => {
    const { data } = get();
    const seeded = seedCarModels(count);

    if (typeof window !== "undefined" && window.mgApi?.contentBulkUpsertCarModels && hasDbConfigured(data.settings)) {
      await window.mgApi.contentBulkUpsertCarModels({
        items: seeded.map((c) => ({
          id: c.id,
          make: c.make,
          model: c.model,
          trim: c.trim,
          year: c.year,
          category: c.category,
        })),
      });
      set({ data: { ...data, carModels: [...seeded, ...data.carModels] } });
      return;
    }

    const next = { ...data, carModels: [...seeded, ...data.carModels] };
    await get().persist(next);
  },
  upsertImageSample: async (item) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItem = { ...item, tags: item.tags ?? [], updatedAt };
    const exists = data.imageSamples.some((x) => x.id === item.id);
    const next = {
      ...data,
      imageSamples: exists ? data.imageSamples.map((x) => (x.id === item.id ? nextItem : x)) : [nextItem, ...data.imageSamples],
    };
    await get().persist(next);
  },
  deleteImageSample: async (id) => {
    const { data } = get();
    const next = { ...data, imageSamples: data.imageSamples.filter((x) => x.id !== id) };
    await get().persist(next);
  },
  upsertPromptTemplate: async (item) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItem = { ...item, updatedAt };

    if (typeof window !== "undefined" && window.mgApi?.contentUpsert && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentUpsert({ kind: "promptTemplates", item: nextItem });
      if (res?.ok) {
        const out = { ...nextItem, ...res.item };
        const exists = data.promptTemplates.some((x) => x.id === out.id);
        const nextList = exists
          ? data.promptTemplates.map((x) => (x.id === out.id ? out : x))
          : [out, ...data.promptTemplates];
        set({ data: { ...data, promptTemplates: nextList } });
      }
      return;
    }

    const exists = data.promptTemplates.some((x) => x.id === item.id);
    const next = {
      ...data,
      promptTemplates: exists
        ? data.promptTemplates.map((x) => (x.id === item.id ? nextItem : x))
        : [nextItem, ...data.promptTemplates],
    };
    await get().persist(next);
  },
  deletePromptTemplate: async (id) => {
    const { data } = get();

    if (typeof window !== "undefined" && window.mgApi?.contentDelete && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentDelete({ kind: "promptTemplates", id });
      if (res?.ok) set({ data: { ...data, promptTemplates: data.promptTemplates.filter((x) => x.id !== id) } });
      return;
    }

    const next = { ...data, promptTemplates: data.promptTemplates.filter((x) => x.id !== id) };
    await get().persist(next);
  },
  upsertTextStyle: async (item) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItem = { ...item, updatedAt };

    if (typeof window !== "undefined" && window.mgApi?.contentUpsert && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentUpsert({ kind: "textStyles", item: nextItem });
      if (res?.ok) {
        const out = { ...nextItem, ...res.item };
        const exists = data.textStyles.some((x) => x.id === out.id);
        const nextList = exists ? data.textStyles.map((x) => (x.id === out.id ? out : x)) : [out, ...data.textStyles];
        set({ data: { ...data, textStyles: nextList } });
      }
      return;
    }

    const exists = data.textStyles.some((x) => x.id === item.id);
    const next = {
      ...data,
      textStyles: exists ? data.textStyles.map((x) => (x.id === item.id ? nextItem : x)) : [nextItem, ...data.textStyles],
    };
    await get().persist(next);
  },
  deleteTextStyle: async (id) => {
    const { data } = get();

    if (typeof window !== "undefined" && window.mgApi?.contentDelete && hasDbConfigured(data.settings)) {
      const res = await window.mgApi.contentDelete({ kind: "textStyles", id });
      if (res?.ok) set({ data: { ...data, textStyles: data.textStyles.filter((x) => x.id !== id) } });
      return;
    }

    const next = { ...data, textStyles: data.textStyles.filter((x) => x.id !== id) };
    await get().persist(next);
  },
  replaceTextStyles: async (items) => {
    const { data } = get();
    const updatedAt = nowIso();
    const nextItems = (items ?? []).map((x) => ({ ...x, updatedAt }));

    if (typeof window !== "undefined" && window.mgApi?.contentBulkUpsertTextStyles && hasDbConfigured(data.settings)) {
      await window.mgApi.contentBulkUpsertTextStyles({ items: nextItems.map((x) => ({
        id: x.id,
        name: x.name,
        presetId: x.presetId,
        paletteId: x.paletteId,
        title: x.title,
        subtitle: x.subtitle,
        subtitle2: x.subtitle2,
        prompt: x.prompt,
        opacity: x.opacity,
        position: x.position,
      })) });
      set({ data: { ...data, textStyles: nextItems } });
      return;
    }

    const next = { ...data, textStyles: nextItems };
    await get().persist(next);
  },
  addHistory: async (item) => {
    const id = createId("hist");
    const { status, ...rest } = item;
    const entry: HistoryItem = {
      id,
      createdAt: nowIso(),
      status: status ?? "ok",
      kind: (rest as Partial<HistoryItem>).kind,
      ...(rest as Omit<HistoryItem, "id" | "createdAt">),
    };
    const { data } = get();
    const next = { ...data, history: [entry, ...data.history].slice(0, 2000) };
    set({ data: next });
    await dataClient.appendHistory(entry);
  },
  resetAll: async () => {
    const next = await dataClient.reset();
    const normalized: AppData = {
      ...emptyData,
      ...next,
      songs: (next as Partial<AppData>).songs ?? [],
      settings: { ...emptyData.settings, ...(next as Partial<AppData>).settings },
      history: (next as Partial<AppData>).history ?? [],
    };
    set({
      data: normalized,
      currentDescription: normalized.descriptions[0]?.content ?? "",
      currentStructure: normalized.structures[0]?.content ?? "",
      currentSongId: normalized.songs[0]?.id ?? null,
      thumbnailUrl: null,
      running: false,
      footerText: "Ready",
      footerProgress: null,
    });
  },
  refreshDbContent: async () => {
    const { data } = get();
    if (!hasDbConfigured(data.settings)) return;
    if (!window.mgApi?.contentBootstrap) return;
    const res = await window.mgApi.contentBootstrap();
    if (!res.ok) return;
    const next: AppData = {
      ...data,
      carModels: res.carModels,
      promptTemplates: res.promptTemplates.map((t) => ({
        id: t.id,
        name: t.name,
        scene: t.scene,
        negativePrompt: t.negativePrompt,
        updatedAt: t.updatedAt,
      })),
      structures: res.structures.map((s) => ({
        id: s.id,
        name: s.name,
        content: s.text,
        updatedAt: s.updatedAt,
      })),
      descriptions: res.descriptions.map((d) => ({
        id: d.id,
        name: d.name,
        content: d.text,
        updatedAt: d.updatedAt,
      })),
      textStyles: res.textStyles,
    };
    set({
      data: next,
      currentDescription: next.descriptions[0]?.content ?? get().currentDescription,
      currentStructure: next.structures[0]?.content ?? get().currentStructure,
    });
  },
}));

