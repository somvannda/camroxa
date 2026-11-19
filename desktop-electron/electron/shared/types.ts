import type { BindingOptions, BindingSelection } from "./pipeline";

export type ApiMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface ApiRequest {
  method: ApiMethod;
  path: string;
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

export type BootstrapDestination = "login" | "confirm_email" | "onboarding" | "app";

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
