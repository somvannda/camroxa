export type ISODateString = string;

export type JobType = "workflow" | "merge" | "suno";

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type WorkflowAction = "generate" | "submit" | "repeat_steps" | "run" | "evaluate" | "export" | "update_prompt";

export type JobPayload =
  | {
      jobType: "workflow";
      action: WorkflowAction;
      description?: string;
      structure?: string;
      descriptionTitle?: string;
      structureTitle?: string;
      language?: string;
      creativity?: number;
      songDraftProvider?: "deepseek" | "slai";
      deepseekApiKey?: string;
      openaiApiKey?: string;
      slaiSongApiKey?: string;
      slaiSongModel?: string;
      batchId?: string;
      batchIndex?: number;
      uniqueOpening?: boolean;
      strictLevel?: 1 | 2 | 3 | 4 | 5;
      uniquenessHistoryWindow?: 50 | 100 | 200 | 500 | 1500;
      sunoAutoSubmit?: boolean;
      sunoApiKey?: string;
      sunoCallbackUrl?: string;
      sunoVersion?: "v5" | "v5.5";
      sunoOutputDirOk?: string;
      sunoOutputDirAlt?: string;
      sunoRunLabel?: string;
      profileOkId?: string;
      profileAltId?: string;
      avoidTitles?: string[];
      avoidAlbums?: string[];
      avoidOpenings?: string[];
      db?: { host: string; port: number; user: string; password: string; database: string };
      forcedTitle?: string;
      forcedAlbum?: string;
      forcedOpening?: string;
    }
  | {
      jobType: "merge";
      versionType: "OK" | "ALT";
      chunkSize: number;
      inputDir: string;
      outputDir: string;
      ffmpegPath: string;
    }
  | {
      jobType: "suno";
      batchId: string;
      expectedCount: number;
      version?: "v5" | "v5.5";
      songs?: Song[];
      profileOkId?: string;
      profileAltId?: string;
      sunoRunLabel?: string;
      db?: { host: string; port: number; user: string; password: string; database: string };
      downloadsDir?: string;
      mergedDir?: string;
      ffmpegPath?: string;
      mergeEnabled?: boolean;
      mergeGroupSize?: number;
      sunoTimeoutMs?: number;
      sunoRetryCount?: number;
      sunoApiKey?: string;
      sunoOutputDir?: string;
      sunoOutputDirOk?: string;
      sunoOutputDirAlt?: string;
      sunoCallbackUrl?: string;
    };

export type JobEvent = {
  jobId: string;
  jobType: JobType;
  status: JobStatus;
  message: string;
  progress?: number;
  action?: WorkflowAction;
  versionType?: "OK" | "ALT";
  song?: Song;
  createdAt: ISODateString;
};

export type SavedText = {
  id: string;
  name: string;
  content: string;
  matchKey?: string;
  updatedAt: ISODateString;
};

export type CarModel = {
  id: string;
  make: string;
  model: string;
  trim: string;
  year: number;
  category: string;
  updatedAt: ISODateString;
};

export type ImageSample = {
  id: string;
  filePath: string;
  tags: string[];
  updatedAt: ISODateString;
};

export type ImageSampleFile = {
  filePath: string;
  fileUrl: string;
  fileName: string;
  mtimeMs: number;
};

export type ImageGenCostEstimate = {
  minUsd: number;
  maxUsd: number;
};

export type ImageGenMeta = {
  provider: "openai" | "slai";
  endpoint: string;
  model: string;
  attempts: number;
  size: string;
  cost?: ImageGenCostEstimate;
};

export type VideoExportSettings = {
  resolution: "1920x1080" | "1080x1920" | "1280x720" | "2560x1440" | "3840x2160";
  fps: 24 | 30 | 60;
  codec: "h264";
  preset: "fast" | "medium" | "slow";
  crf: number;
  audioBitrateKbps: 128 | 192 | 256;
};

export type VideoMergeItemStatus = "pending" | "running" | "done" | "failed";

export type VideoMergeEvent = {
  runId: string;
  index: number;
  total: number;
  directory: string;
  status: VideoMergeItemStatus;
  message: string;
  outputPath?: string;
};

export type VideoRenderItemStatus = "pending" | "running" | "done" | "failed";

export type VideoRenderStartInput = {
  mp3Path: string;
  backgroundPath: string;
  outputDir: string;
  templatePath?: string;
  templateJsonB64?: string;
  logoPath?: string;
  fps?: number;
  width?: number;
  height?: number;
  renderer?: "gpu" | "cpu";
  previewPngPath?: string;
  previewFrame?: number;
};

export type VideoTemplateListItem = {
  label: string;
  path: string;
  source: "builtin" | "user";
};

export type VideoRenderEvent = {
  runId: string;
  status: VideoRenderItemStatus;
  message: string;
  progress?: number;
  frame?: number;
  totalFrames?: number;
  outputPath?: string;
};

export type PromptTemplate = {
  id: string;
  name: string;
  scene: string;
  negativePrompt: string;
  updatedAt: ISODateString;
};

export type TextStyle = {
  id: string;
  name: string;
  presetId?: string;
  paletteId?: string;
  title: string;
  subtitle: string;
  subtitle2: string;
  prompt: string;
  opacity: number;
  position: "top" | "center" | "bottom";
  updatedAt: ISODateString;
};

export type ContentKind = "promptTemplates" | "structures" | "descriptions" | "textStyles" | "carModels";

export type DbSavedTextRow = { id: string; name: string; text: string; matchKey?: string; updatedAt: ISODateString };

export type UpsertSavedTextInput = { id: string; name: string; text: string; matchKey?: string };
export type DbPromptTemplateRow = { id: string; name: string; scene: string; negativePrompt: string; updatedAt: ISODateString };

export type UpsertPromptTemplateInput = { id: string; name: string; scene: string; negativePrompt: string };
export type UpsertCarModelInput = { id: string; make: string; model: string; trim: string; year: number; category: string };
export type UpsertTextStyleInput = {
  id: string;
  name: string;
  presetId?: string;
  paletteId?: string;
  title: string;
  subtitle: string;
  subtitle2: string;
  prompt: string;
  opacity: number;
  position: "top" | "center" | "bottom";
};

export type ContentBootstrapOk = {
  ok: true;
  promptTemplates: DbPromptTemplateRow[];
  structures: DbSavedTextRow[];
  descriptions: DbSavedTextRow[];
  textStyles: TextStyle[];
  carModels: CarModel[];
};
export type ContentBootstrapResult = ContentBootstrapOk | { ok: false; message: string };

export type ContentUpsertRequest =
  | { kind: "promptTemplates"; item: UpsertPromptTemplateInput }
  | { kind: "structures"; item: UpsertSavedTextInput }
  | { kind: "descriptions"; item: UpsertSavedTextInput }
  | { kind: "textStyles"; item: UpsertTextStyleInput }
  | { kind: "carModels"; item: UpsertCarModelInput };

export type ContentUpsertResult = { ok: true; item: { id: string; updatedAt: ISODateString } & Record<string, unknown> } | { ok: false; message: string };

export type ContentDeleteRequest = { kind: ContentKind; id: string };
export type ContentDeleteResult = { ok: true } | { ok: false; message: string };

export type ContentBulkUpsertTextStylesRequest = { items: UpsertTextStyleInput[] };
export type ContentBulkUpsertTextStylesResult = { ok: true; updatedAt: ISODateString } | { ok: false; message: string };

export type ContentBulkUpsertCarModelsRequest = { items: UpsertCarModelInput[] };
export type ContentBulkUpsertCarModelsResult = { ok: true; updatedAt: ISODateString } | { ok: false; message: string };

export type HistoryItem = {
  id: string;
  path: string;
  task: string;
  createdAt: ISODateString;
  status: "ok" | "running" | "error";
  kind?: "song" | "system" | "job" | "thumbnail" | "merge";
};

export type Song = {
  id: string;
  title: string;
  album: string;
  lyricsRaw: string;
  lyricsPolished: string;
  batchIndex?: number;
  songDescriptionTitle?: string;
  songStructureTitle?: string;
  songDescription: string;
  songStructure: string;
  profileOkId?: string;
  profileAltId?: string;
  profileOkName?: string;
  profileAltName?: string;
  language: string;
  creativity: number;
  batchId?: string;
  createdAt: ISODateString;
};

export type SongDraft = {
  id: string;
  title: string;
  album: string;
};

export type Profile = {
  id: string;
  name: string;
  folderName: string;
  runPrefix: string;
  logoPath: string;
  createdAt: ISODateString;
  updatedAt: ISODateString;
};

export type Settings = {
  language: "English" | "German" | "Spanish" | "French";
  creativity: number;
  sort: number;
  template: string;
  activeProfileId: string | null;
  activeProfileOkId: string | null;
  activeProfileAltId: string | null;
  channelOkProfileIds: string[];
  channelAltProfileIds: string[];
  activeDescriptionIds: string[];
  activeStructureIds: string[];
  matchDescriptionStructure: boolean;
  showLatest: boolean;
  shuffle: boolean;
  shuffleDescription: boolean;
  shuffleStructure: boolean;
  enabledDescriptionIds: string[];
  enabledStructureIds: string[];
  uniqueOpening: boolean;
  strictLevel: 1 | 2 | 3 | 4 | 5;
  uniquenessHistoryWindow: 50 | 100 | 200 | 500 | 1500;
  cycleStructures: boolean;
  mergeChunkSize: number;
  songDraftProvider: "deepseek" | "slai";
  deepseekApiKey: string;
  openaiApiKey: string;
  slaiSongApiKey: string;
  slaiSongModel: string;
  slaiImgApiKey: string;
  slaiImgModel: string;
  ffmpegPath: string;
  pythonPath: string;
  downloadsDir: string;
  mergedDir: string;
  defaultSongCount: number;
  imageOutputDir: string;
  imageResolution: "1920x1080" | "1080x1920";
  styleStrength: number;
  backgroundSourceMode?: "samples" | "prompt";
  thumbnailOverlayMode?: "ai";
  backgroundTemplateCycleIndex: number;
  imageSamplesDir?: string;
  videoMergeDirectories: string[];
  videoExport: VideoExportSettings;
  videoRenderOutputDir: string;
  videoRenderTemplatePath: string;
  videoRenderBackgroundPath: string;
  autoGenSongs: boolean;
  autoGenImage: boolean;
  autoGSuno: boolean;
  sunoTimeoutMs: number;
  sunoRetryCount: number;
  sunoDefaultVersion: "v5" | "v5.5";
  sunoMergeEnabled: boolean;
  sunoMergeGroupSize: number;
  sunoApiKey: string;
  sunoOutputDir: string;
  sunoCallbackUrl: string;
  dbHost: string;
  dbPort: number;
  dbUser: string;
  dbPassword: string;
  dbName: string;
};

export type AppData = {
  descriptions: SavedText[];
  structures: SavedText[];
  songs: Song[];
  songDrafts: SongDraft[];
  profiles: Profile[];
  carModels: CarModel[];
  imageSamples: ImageSample[];
  promptTemplates: PromptTemplate[];
  textStyles: TextStyle[];
  history: HistoryItem[];
  settings: Settings;
};
