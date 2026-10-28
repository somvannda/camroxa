import { musicAuthFetch } from "@/lib/auth-fetch";
import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";

export type WebMusicModel = "V6" | "V6_MINI" | "V6_WILD";

export type WebMusicGenerateInput = {
  mode: "simple" | "advanced";
  lyrics?: string;
  style?: string;
  title?: string;
  prompt?: string;
  instrumental?: boolean;
  model?: WebMusicModel;
  negative_tags?: string;
  vocal_gender?: "m" | "f" | "both";
  style_weight?: number;
  weirdness_constraint?: number;
  audio_weight?: number;
  workspace_id?: string;
};

export type WebMusicQuota = {
  limit: number;
  used: number;
  remaining: number;
  is_pro?: boolean;
  requires_upgrade?: boolean;
  credits_remaining?: number;
  credits_per_song?: number;
  has_subscription?: boolean;
  can_download?: boolean;
  daily_free_remaining?: number;
  daily_free_limit?: number;
  premium_unlocked?: boolean;
  free_model?: string;
  queue_limit?: number;
  queue_used?: number;
  previews?: {
    eligible: boolean;
    seconds: number;
    models: Array<{
      model: string;
      label: string;
      limit: number;
      used: number;
      remaining: number;
      seconds: number;
    }>;
  } | null;
};

export type WebMusicWorkspace = {
  id: string;
  name: string;
  is_default?: boolean;
  created_at?: string | null;
};

export type WebMusicGenerationPage = {
  items: WebMusicGeneration[];
  total: number;
  limit: number;
  offset: number;
};

export type WebMusicPlaylistSummary = {
  id: string;
  name: string;
  slug?: string;
  description?: string | null;
  is_public?: boolean;
  song_count?: number;
  updated_at?: string | null;
};

export type WebMusicPlaylistItem = {
  id: string;
  task_id: string;
  variant: string;
  position: number;
  title: string;
  style?: string;
  status?: string;
  ready?: boolean;
  package_status?: string;
  audio_url?: string;
  image_url?: string | null;
  added_at?: string | null;
};

export type WebMusicStudioProject = {
  id: string;
  title: string;
  major_version: number;
  bpm: number;
  time_signature: string;
  pinned?: boolean;
  archived?: boolean;
  tags?: string[];
  comment_count?: number;
  last_comment_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ErrorBody = {
  detail?:
    | string
    | { message?: string }
    | Array<{ msg?: string; loc?: Array<string | number> }>;
  error?: {
    message?: string;
    code?: string;
    details?: { requires_upgrade?: boolean; retry_after?: number };
  };
  message?: string;
};

export class WebMusicApiError extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    retryAfterSeconds: number | null = null,
    code: string | null = null
  ) {
    super(message);
    this.name = "WebMusicApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
    this.code = code;
  }
}

function parseRetryAfterSeconds(value: string | null): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return Math.max(0, Number.parseInt(trimmed, 10));
  const when = Date.parse(trimmed);
  if (Number.isNaN(when)) return null;
  return Math.max(0, Math.ceil((when - Date.now()) / 1000));
}

function retryAfterFromBody(data: ErrorBody): number | null {
  const raw = data.error?.details?.retry_after;
  if (raw == null) return null;
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

async function readError(response: Response, fallback: string) {
  const headerRetry = parseRetryAfterSeconds(response.headers.get("retry-after"));
  try {
    const data = (await response.json()) as ErrorBody;
    const retryAfterSeconds = headerRetry ?? retryAfterFromBody(data);
    if (data.error?.message) {
      return { message: data.error.message, code: data.error.code ?? null, retryAfterSeconds };
    }
    if (typeof data.detail === "string") {
      return { message: data.detail, code: data.error?.code ?? null, retryAfterSeconds };
    }
    if (data.detail && typeof data.detail === "object" && !Array.isArray(data.detail) && data.detail.message) {
      return { message: data.detail.message, code: data.error?.code ?? null, retryAfterSeconds };
    }
    if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      return { message: data.detail[0].msg, code: data.error?.code ?? null, retryAfterSeconds };
    }
    if (typeof data.message === "string") {
      return { message: data.message, code: data.error?.code ?? null, retryAfterSeconds };
    }
  } catch {
    /* ignore */
  }
  return { message: fallback, code: null, retryAfterSeconds: headerRetry };
}

async function rejectResponse(response: Response, fallback: string): Promise<never> {
  const parsed = await readError(response, fallback);
  let message = parsed.message;
  if ([502, 503, 504].includes(response.status) && /bad gateway|request failed/i.test(message)) {
    message = "AI assist is temporarily unavailable. Please try again in a moment.";
  }
  throw new WebMusicApiError(message, response.status, parsed.retryAfterSeconds, parsed.code);
}

async function musicJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) await rejectResponse(response, `Request failed (${response.status})`);
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchWebMusicQuota(): Promise<WebMusicQuota> {
  return musicJson<WebMusicQuota>("/api/v3/web-music/quota");
}

export async function listWebMusicWorkspaces(): Promise<{ items: WebMusicWorkspace[] }> {
  return musicJson("/api/v3/web-music/workspaces");
}

export async function createWebMusicWorkspace(name: string): Promise<WebMusicWorkspace> {
  return musicJson("/api/v3/web-music/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function updateWebMusicWorkspace(
  workspaceId: string,
  name: string
): Promise<WebMusicWorkspace> {
  return musicJson(`/api/v3/web-music/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function listWebMusicPlaylists(): Promise<{ items: WebMusicPlaylistSummary[] }> {
  return musicJson("/api/v3/web-music/playlists");
}

export async function addWebMusicPlaylistItem(
  playlistId: string,
  taskId: string,
  variant = "ok"
): Promise<{ id: string }> {
  return musicJson(`/api/v3/web-music/playlists/${encodeURIComponent(playlistId)}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, variant }),
  });
}

export async function createWebMusicPlaylist(name: string): Promise<WebMusicPlaylistSummary> {
  return musicJson("/api/v3/web-music/playlists", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, is_public: false }),
  });
}

export async function generateWebMusicStyles(input: {
  style?: string;
  lyrics?: string;
  title?: string;
  description?: string;
  prompt?: string;
}): Promise<{ style: string; credits_charged?: number }> {
  return musicJson("/api/v3/web-music/generate-styles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      style: input.style ?? "",
      lyrics: (input.lyrics ?? "").slice(0, 400),
      title: input.title ?? "",
      description: input.description ?? "",
      prompt: input.prompt ?? "",
    }),
  });
}

export async function generateWebMusicDraft(prompt: string): Promise<{ lyrics: string; title: string }> {
  return musicJson("/api/v3/web-music/generate-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
}

export async function generateWebMusic(
  input: WebMusicGenerateInput
): Promise<{
  task_id: string;
  status: string;
  title: string;
  style: string;
  model?: string;
  model_label?: string;
  is_preview?: boolean;
  unlockable?: boolean;
  preview_seconds?: number | null;
  quota: WebMusicQuota;
}> {
  return musicJson("/api/v3/web-music/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listWebMusicGenerations(
  limit = 40,
  offset = 0,
  workspaceId?: string
): Promise<WebMusicGenerationPage> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (workspaceId) params.set("workspace_id", workspaceId);
  return musicJson<WebMusicGenerationPage>(`/api/v3/web-music/generations?${params.toString()}`);
}

export async function getWebMusicGeneration(id: string): Promise<WebMusicGeneration> {
  return musicJson<WebMusicGeneration>(`/api/v3/web-music/generations/${encodeURIComponent(id)}`);
}

export async function updateWebMusicGenerationTitle(
  id: string,
  title: string,
  variant?: string
): Promise<WebMusicGeneration> {
  return musicJson<WebMusicGeneration>(`/api/v3/web-music/generations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, ...(variant ? { variant } : {}) }),
  });
}

export async function deleteWebMusicGeneration(id: string): Promise<void> {
  await musicJson<void>(`/api/v3/web-music/generations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function unlockWebMusicPreview(id: string): Promise<WebMusicGeneration> {
  return musicJson<WebMusicGeneration>(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}/unlock-preview`,
    { method: "POST" }
  );
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function fetchWebMusicClipBlob(id: string, variant: string): Promise<Blob> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}/download?variant=${encodeURIComponent(variant)}`
  );
  if (!response.ok) await rejectResponse(response, "MP3 download failed");
  return response.blob();
}

export async function fetchWebMusicClipWavBlob(id: string, variant: string): Promise<Blob> {
  let lastError = "WAV download failed";
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const response = await musicAuthFetch(
      `/api/v3/web-music/generations/${encodeURIComponent(id)}/download-wav?variant=${encodeURIComponent(variant)}`
    );
    if (response.ok) return response.blob();
    const parsed = await readError(response, "WAV download failed");
    lastError = parsed.message;
    if (!/not ready yet|try again/i.test(lastError) || attempt === 7) {
      throw new WebMusicApiError(lastError, response.status, parsed.retryAfterSeconds, parsed.code);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2500));
  }
  throw new Error(lastError);
}

export async function fetchWebMusicTimedLyricsBlob(
  id: string,
  variant: string,
  format: "lrc" | "srt"
): Promise<Blob> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${encodeURIComponent(format)}`
  );
  if (!response.ok) await rejectResponse(response, "Timed lyrics download failed");
  return response.blob();
}

export async function downloadWebMusicClip(id: string, variant: string, filename: string): Promise<void> {
  saveBlob(await fetchWebMusicClipBlob(id, variant), filename);
}

export async function downloadWebMusicClipWav(id: string, variant: string, filename: string): Promise<void> {
  saveBlob(await fetchWebMusicClipWavBlob(id, variant), filename);
}

export async function downloadWebMusicTimedLyrics(
  id: string,
  variant: string,
  format: "lrc" | "srt",
  filename: string
): Promise<void> {
  saveBlob(await fetchWebMusicTimedLyricsBlob(id, variant, format), filename);
}

export function clipVariantLabel(variant?: string | null): string {
  return variant === "alt" ? "Version 2" : "Version 1";
}

export function clipFilename(
  generation: Pick<WebMusicGeneration, "title" | "id">,
  clip: Pick<WebMusicClip, "variant" | "title">,
  extension: string
): string {
  const name = clip.title || generation.title || generation.id;
  return `${name} - ${clipVariantLabel(clip.variant)}.${extension}`.replace(/[\\/:*?"<>|]+/g, "-");
}

/** Generation keys the viewer has liked, formatted `${generationId}:${variant}`. */
export async function fetchWebMusicLikedKeys(): Promise<string[]> {
  const data = await musicJson<{ keys?: string[] }>("/api/v3/web-music/likes/keys");
  return Array.isArray(data?.keys) ? data.keys : [];
}

export async function likeWebMusicGeneration(
  id: string,
  variant: string,
  liked: boolean
): Promise<void> {
  await musicJson(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}/like?variant=${encodeURIComponent(variant)}`,
    { method: liked ? "PUT" : "DELETE" }
  );
}

export async function listWebMusicPlaylistItems(
  playlistId: string
): Promise<{ items: WebMusicPlaylistItem[] }> {
  return musicJson<{ items: WebMusicPlaylistItem[] }>(
    `/api/v3/web-music/playlists/${encodeURIComponent(playlistId)}/items`
  );
}

export async function deleteWebMusicPlaylist(playlistId: string): Promise<void> {
  await musicJson<void>(`/api/v3/web-music/playlists/${encodeURIComponent(playlistId)}`, {
    method: "DELETE",
  });
}

export async function listWebMusicStudioProjects(
  limit = 40,
  offset = 0
): Promise<{
  items: WebMusicStudioProject[];
  total: number;
  limit: number;
  offset: number;
}> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return musicJson(`/api/v3/web-music/studio/projects?${params.toString()}`);
}

export type WebMusicStudioUpload = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  duration_seconds?: number | null;
  url: string;
  created_at?: string | null;
};

export type WebMusicStudioClipResult = {
  id?: string;
  title?: string;
  audioUrl?: string;
  imageUrl?: string;
};

export type WebMusicStudioOperation = {
  id: string;
  status: string;
  operation_type: string;
  mode: string;
  task_id?: string | null;
  error_message?: string | null;
  result?: { clips?: WebMusicStudioClipResult[] } | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export async function uploadWebMusicStudioAudio(
  file: File,
  durationSeconds?: number
): Promise<WebMusicStudioUpload> {
  const form = new FormData();
  form.append("file", file);
  if (durationSeconds && Number.isFinite(durationSeconds)) {
    form.append("duration_seconds", String(durationSeconds));
  }
  return musicJson<WebMusicStudioUpload>("/api/v3/web-music/studio/uploads", {
    method: "POST",
    body: form,
  });
}

export async function extendWebMusicStudioUpload(
  uploadId: string,
  input: { prompt?: string; title?: string; tags?: string; continue_at?: number } = {}
): Promise<WebMusicStudioOperation> {
  return musicJson(`/api/v3/web-music/studio/uploads/${encodeURIComponent(uploadId)}/extend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function coverWebMusicStudioUpload(
  uploadId: string,
  input: { prompt?: string; title?: string; tags?: string; cover_start_s?: number; cover_end_s?: number } = {}
): Promise<WebMusicStudioOperation> {
  return musicJson(`/api/v3/web-music/studio/uploads/${encodeURIComponent(uploadId)}/cover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function getWebMusicStudioOperation(id: string): Promise<WebMusicStudioOperation> {
  return musicJson(`/api/v3/web-music/studio/operations/${encodeURIComponent(id)}`);
}
export async function listWebMusicStudioOperations(
  limit = 20,
  operationType?: string
): Promise<{ items: WebMusicStudioOperation[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (operationType) params.set("operation_type", operationType);
  return musicJson(`/api/v3/web-music/studio/operations?${params.toString()}`);
}