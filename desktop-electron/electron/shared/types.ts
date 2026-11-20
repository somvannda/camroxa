import type { BindingOptions, BindingSelection } from "./pipeline";

export type ApiMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface ApiRequest {
  method: ApiMethod;
  path: string;
  /** API surface to call. Defaults to the desktop base (`/api/v1`). */
  apiVersion?: "v1" | "v2" | "v3";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  auth?: boolean;
  timeoutMs?: number;
}

export interface ApiError {
  code: string;
  message: string;
  detail?: unknown;
  requestId?: string;
  retryable?: boolean;
}

export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

export interface ApiResponse {
  status: number;
  data: unknown;
  headers: Record<string, string>;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface SessionSummary {
  userId: string;
  email: string;
  displayName: string;
  accessExpiresAt: number;
}

export interface SavedAccount {
  userId: string;
  email: string;
  displayName: string;
  lastUsedAt: number;
}

export type BootstrapDestination = "login" | "confirm_email" | "app";

export interface BootstrapResult {
  destination: BootstrapDestination;
  session: SessionSummary | null;
  message?: string;
  code?: string;
  portalUrl?: string;
}

export interface UserMe {
  id: string;
  email: string;
  email_confirmed: boolean;
  display_name: string;
  credit_balance: number;
  plan_name?: string | null;
  role?: string | null;
  onboarding_paid?: boolean;
  desktop_access?: boolean | null;
  channel_profile_count?: number;
}

export interface AppInfo {
  name: string;
  version: string;
  env: string;
  platform: string;
  electron: string;
  chrome: string;
  node: string;
  devBypass: boolean;
  portalUrl: string;
  build: string;
  apiBaseUrl: string;
}

export interface UpdateOffer {
  version: string;
  mandatory: boolean;
  notes?: string;
  url?: string;
  publishedAt?: string;
}

export interface UpdateCheckResult {
  currentVersion: string;
  offer: UpdateOffer | null;
  message?: string;
}

/** Preferences that belong to this computer, not the account. */
export interface DevicePreferences {
  ffmpegPath: string;
  sunoOutputDir: string;
}

export interface PickFileRequest {
  kind: "file" | "directory";
  title?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
  multiple?: boolean;
}

export type TemplateSchema = "vizzy" | "legacy";

export interface InstalledTemplate {
  id: string;
  name: string;
  kind: string;
  schemaVersion: number;
  schema: TemplateSchema;
  path: string;
  thumbnailPath: string | null;
  marketplaceItemId: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface InstallTemplateRequest {
  itemId: string;
  name?: string;
  kind?: string;
  previewUrl?: string;
  reinstall?: boolean;
}

export interface InstallTemplateResult {
  uid: string;
  name: string;
  kind: string;
  schema: TemplateSchema;
  reinstalled: boolean;
}

export interface TemplateChangedEvent {
  uid: string;
  itemId: string;
  reinstalled: boolean;
}

/* ------------------------------------------------------------------ */
/* Vizzy host (P7)                                                     */
/* ------------------------------------------------------------------ */

/** Placement of the hosted editor view inside the window, in CSS pixels. */
export interface VizzyBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Everything the Vizzy shell strip renders. */
export interface VizzyState {
  attached: boolean;
  ready: boolean;
  crashed: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  /** Project composition size/fps; the export popover seeds its defaults from these. */
  projectWidth: number;
  projectHeight: number;
  projectFps: number;
  projectDuration: number;
  fftTier: string;
  crossOriginIsolated: boolean;
  path: string | null;
  error: string | null;
}

/** `vizzy:probe` — live editor diagnostics read from `window.__vizzyTest`. */
export interface VizzyProbe {
  url: string;
  ready: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  crossOriginIsolated: boolean;
  fftTier: string;
  webgl2: boolean;
}

export interface VizzySaveResult {
  path: string;
  name: string;
  bytes: number;
}

export interface VizzyOpenResult {
  path: string;
  name: string;
  nodeCount: number;
}

/** Shell-facing summary of a saved video template. */
export interface VideoTemplateInfo {
  id: string;
  name: string;
  kind: "long" | "reel";
  width: number;
  height: number;
  fps: number;
  createdAt: string;
  thumbnailUrl: string | null;
}

/** `video-templates:changed` (main → every shell window). */
export interface VideoTemplateChangedEvent {
  id: string;
  action: "saved" | "deleted";
}

/**
 * `vizzy:template-options` — what the save dialog needs from the live project.
 * The options come from the exact snapshot the save will capture.
 */
export interface VizzyTemplateDraftInfo {
  name: string;
  width: number;
  height: number;
  fps: number;
  kind: "long" | "reel";
  /** Binding pre-fill from `detectBindings()`, filtered to compatible options. */
  detected: BindingSelection;
  options: BindingOptions;
}

/** `vizzy:save-template` request; the host supplies the snapshot and thumbnail. */
export interface VizzySaveTemplateInput {
  name: string;
  kind: "long" | "reel";
  bindings: BindingSelection;
}

/** `vizzy:render-template` — one saved template rendered with a real track. */
export interface VizzyRenderTemplateRequest {
  templateId: string;
  audioPath: string;
  title?: string;
  artist?: string;
  album?: string;
  backgroundPath?: string;
  logoPath?: string;
  palette?: string[];
}

/** `vizzy:export` request: every field is optional; the project fills the gaps. */
export interface VizzyExportSettingsInput {
  width?: number;
  height?: number;
  fps?: number;
  format?: "mp4" | "webm";
  codec?: "h264" | "vp8" | "vp9";
  /** Video bitrate in Mbps; 0 lets the encoder choose a CRF. */
  bitrate?: number;
  crf?: number;
  start?: number;
  end?: number;
}

/** `vizzy:export:progress` payload (main → shell event). */
export interface VizzyExportProgress {
  jobId: string;
  done: number;
  total: number;
  percent: number;
  stage: string;
}

export interface VizzyExportResult {
  jobId: string;
  /** Absolute path inside `<userData>/renders/`; the shell only basenames it. */
  path: string;
  name: string;
  bytes: number;
  frames: number;
  durationSec: number;
  width: number;
  height: number;
  videoCodec: string | null;
  audioCodec: string | null;
  elapsedMs: number;
}

export type VizzyExportOutcome =
  | { status: "done"; result: VizzyExportResult }
  | { status: "cancelled" }
  | { status: "failed"; message: string };

/** One managed file in `<userData>/renders/`. */
export interface VizzyRenderSummary {
  name: string;
  bytes: number;
  mtimeMs: number;
}

/* ------------------------------------------------------------------ */
/* Video pipeline (P7 batch orchestration)                             */
/* ------------------------------------------------------------------ */

export type PipelineBranch = "long" | "reel";

export type PipelineJobStatus =
  | "queued"
  | "rendering"
  | "encoding"
  | "merging"
  | "done"
  | "failed"
  | "cancelled";

/** One durable queue row, as the shell renders it. */
export interface PipelineJobInfo {
  id: string;
  batchId: string;
  branch: PipelineBranch;
  templateId: string;
  templateName: string;
  audioPath: string;
  audioName: string;
  title: string;
  artist: string;
  album: string;
  outputDir: string;
  status: PipelineJobStatus;
  stage: string;
  progress: number;
  error: string | null;
  /** Absolute path of the validated render, once the row is done. */
  output: string | null;
  merge: boolean;
  createdAt: number;
  updatedAt: number;
}

/** One batch: the queue group the Music trigger enqueues. */
export interface PipelineBatchInfo {
  batchId: string;
  outputDir: string;
  merge: boolean;
  mergedOutput: string | null;
  status: "idle" | "running" | "merging" | "done" | "failed" | "cancelled";
  error: string | null;
  total: number;
  done: number;
  failed: number;
  cancelled: number;
  running: boolean;
  createdAt: number;
  updatedAt: number;
}

export interface PipelineSnapshot {
  running: boolean;
  jobs: PipelineJobInfo[];
  batches: PipelineBatchInfo[];
  /** Set when the render host could not be started (bundle missing, etc.). */
  error: string | null;
}

/** One requested render; the main process resolves audio paths when `audioDir` is set. */
export interface PipelineEnqueueJob {
  branch: PipelineBranch;
  templateId: string;
  audioPath?: string;
  audioDir?: string;
  title?: string;
  artist?: string;
  album?: string;
  backgroundPath?: string;
  logoPath?: string;
}

export interface PipelineEnqueueRequest {
  /** Reuse an existing batch id when retrying; a new one is created otherwise. */
  batchId?: string;
  /** Absolute run folder; renders are managed by the app, the merge lands here. */
  outputDir: string;
  merge?: boolean;
  /** File stem for the merged output, sanitised by the main process. */
  mergeName?: string;
  /** Start the runner as soon as the rows are created (Music action). */
  autostart?: boolean;
  jobs: PipelineEnqueueJob[];
}

export interface PipelineEnqueueSkip {
  audioPath: string;
  title: string;
  reason: string;
}

export interface PipelineEnqueueResult {
  batchId: string;
  created: number;
  skipped: number;
  /** Rows already queued/done for the same key; retry is explicit. */
  duplicates: number;
  skippedDetails: PipelineEnqueueSkip[];
  started: boolean;
  message: string | null;
}

/** `pipeline:changed` payload (main → shell). The shell re-reads the snapshot. */
export interface PipelineChangedEvent {
  batchId: string;
  reason: "enqueued" | "started" | "progress" | "done" | "failed" | "cancelled" | "cleared";
}

/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* Music download coordinator (P4)                                     */
/* ------------------------------------------------------------------ */

export type DownloadItemState = "queued" | "downloading" | "done" | "failed" | "cancelled";

export type DownloadTargetRole = "primary" | "secondary";

/** One pending target, as the shell renders it. No URL: it may be signed. */
export interface DownloadItemInfo {
  key: string;
  taskId: string;
  songId: string | null;
  batchId: string | null;
  title: string;
  trackNumber: number | null;
  role: DownloadTargetRole;
  state: DownloadItemState;
  /** Retry is only possible while the item still holds a download URL. */
  hasUrl: boolean;
  targetPath: string | null;
  receivedBytes: number;
  totalBytes: number | null;
  /** 0…100, or null when the server sent no content length. */
  percent: number | null;
  attempts: number;
  error: string | null;
  errorCode: string | null;
  updatedAt: number;
  completedAt: number | null;
}

export interface DownloadSnapshot {
  items: DownloadItemInfo[];
  /** The coordinator is polling the server. */
  running: boolean;
  /** Downloads were stopped from the shell; queued work resumes on start. */
  paused: boolean;
  active: number;
  concurrency: number;
  /** Absolute output root. Never contains credentials. */
  root: string;
  /** True when no Suno output folder is configured and the managed dir is used. */
  rootIsManaged: boolean;
  lastPolledAt: number | null;
  lastError: string | null;
}

export type DownloadChangedReason =
  | "queued"
  | "started"
  | "progress"
  | "done"
  | "failed"
  | "cancelled"
  | "retried"
  | "paused"
  | "resumed";

/** `downloads:changed` payload (main → shell). The shell re-reads the snapshot. */
export interface DownloadChangedEvent {
  reason: DownloadChangedReason;
  key: string | null;
}

/* ------------------------------------------------------------------ */
/* Manual YouTube upload (Progress row action)                        */
/* ------------------------------------------------------------------ */

/**
 * Why the Upload action is unavailable. `none` means it is available; every
 * other value is shown as a specific reason next to the disabled action.
 */
export type YoutubeUploadBlock =
  | "none"
  | "no-file"
  | "no-channel"
  | "no-token"
  | "quota"
  | "plan"
  | "legacy-template"
  | "already-uploaded"
  | "uploading"
  | "busy"
  | "unavailable";

/** One Progress row the shell wants an upload verdict for. */
export interface YoutubeUploadRowQuery {
  key: string;
  batchId: string;
  profileId: string;
  role: string;
  runDir: string | null;
  youtubeUrl?: string | null;
}

export interface YoutubeUploadRowState {
  key: string;
  profileId: string;
  /** Canonical merged-file path, or null when the run has no merge on disk. */
  mergedPath: string | null;
  mergedName: string | null;
  mergedBytes: number | null;
  block: YoutubeUploadBlock;
  reason: string | null;
}

export interface YoutubePlaylistOption {
  id: string;
  title: string;
}

export interface YoutubeChannelSummary {
  profileId: string;
  profileName: string;
  connected: boolean;
  channelTitle: string | null;
  playlistId: string;
  playlistTitle: string | null;
  /** Playlists the connected channel offers (for “With playlist”). */
  playlists: YoutubePlaylistOption[];
}

export interface YoutubeAvailability {
  /** Channel summary for the first queried profile (back-compat/simple case). */
  channel: YoutubeChannelSummary | null;
  /** One summary per queried profile, so multi-channel accounts stay honest. */
  channels: YoutubeChannelSummary[];
  quotaRemaining: number | null;
  quotaLimit: number | null;
  rows: YoutubeUploadRowState[];
  /** Set when the profiles/connections lookup itself failed. */
  error: string | null;
}

/** What the confirmation dialog shows before anything is uploaded. */
export interface YoutubeUploadPlan {
  key: string;
  profileId: string;
  channelTitle: string;
  title: string;
  description: string;
  visibility: string;
  publishAt: string | null;
  playlistId: string;
  playlistTitle: string | null;
  mergedName: string;
  mergedBytes: number;
  tags: string[];
  category: string;
  madeForKids: boolean;
  containsSyntheticMedia: boolean;
}

export type YoutubeUploadPhase =
  | "queued"
  | "preparing"
  | "uploading"
  | "recording"
  | "done"
  | "failed"
  | "cancelled";

export interface YoutubeUploadStartRequest {
  key: string;
  batchId: string;
  profileId: string;
  role: string;
  runDir: string | null;
  /** `profile` (default), `none`, or a playlist id chosen for this one upload. */
  playlist?: string;
  /** Set when retrying a failed attempt so the same publish job is reused. */
  retryJobUid?: string | null;
}

export interface YoutubeUploadState {
  uploadId: string;
  key: string;
  batchId: string;
  profileId: string;
  phase: YoutubeUploadPhase;
  sentBytes: number;
  totalBytes: number;
  percent: number;
  message: string | null;
  title: string | null;
  videoId: string | null;
  videoUrl: string | null;
  jobUid: string | null;
  error: string | null;
  startedAt: number;
  finishedAt: number | null;
}

export interface YoutubeUploadSnapshot {
  active: YoutubeUploadState | null;
  /** Most recent first, including the active attempt. */
  history: YoutubeUploadState[];
}

/** `youtube:changed` payload (main → shell). */
export interface YoutubeUploadChangedEvent {
  upload: YoutubeUploadState;
}

export function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

export function fail(
  code: string,
  message: string,
  detail?: unknown,
  retryable = false,
): { ok: false; error: ApiError } {
  return { ok: false, error: { code, message, detail, retryable } };
}
