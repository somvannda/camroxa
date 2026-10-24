/** Same-origin music-web generation client. */

import { musicAuthFetch } from '@/lib/auth-fetch';
import { parseRetryAfterSeconds, type WebMusicGenerateInput } from '@/lib/create-submit-queue';

export class MusicApiError extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    retryAfterSeconds: number | null = null,
    code: string | null = null,
  ) {
    super(message);
    this.name = 'MusicApiError';
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
    this.code = code;
  }
}

export type { WebMusicGenerateInput };

export type WebMusicPreviewModel = {
  model: string;
  label: string;
  limit: number;
  used: number;
  remaining: number;
  seconds: number;
};

export type WebMusicPreviews = {
  eligible: boolean;
  seconds: number;
  models: WebMusicPreviewModel[];
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
  previews?: WebMusicPreviews | null;
};

export type WebMusicClip = {
  variant: 'ok' | 'alt' | string;
  label: string;
  audio_url: string;
  download_url: string;
  ready: boolean;
  package_status?: string;
  image_url?: string | null;
  duration_seconds?: number | null;
  title?: string;
  is_preview?: boolean;
  preview_seconds?: number | null;
};

export type WebMusicGeneration = {
  id: string;
  title: string;
  lyrics: string;
  style: string;
  model: string;
  model_label?: string;
  instrumental: boolean;
  status: string;
  error_message?: string | null;
  created_at?: string | null;
  is_preview?: boolean;
  unlockable?: boolean;
  preview_seconds?: number | null;
  negative_tags?: string | null;
  vocal_gender?: string | null;
  style_weight?: number | null;
  weirdness_constraint?: number | null;
  audio_weight?: number | null;
  clips: WebMusicClip[];
};

export type WebMusicWorkspace = {
  id: string;
  name: string;
  is_default?: boolean;
  created_at?: string | null;
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

function retryAfterFromBody(data: ErrorBody): number | null {
  const raw = data.error?.details?.retry_after;
  if (raw == null) return null;
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

async function readError(response: Response, fallback: string): Promise<{
  message: string;
  code: string | null;
  retryAfterSeconds: number | null;
}> {
  const headerRetry = parseRetryAfterSeconds(response.headers.get('retry-after'));
  try {
    const data = (await response.json()) as ErrorBody;
    const bodyRetry = retryAfterFromBody(data);
    const retryAfterSeconds = headerRetry ?? bodyRetry;
    if (data.error?.code === 'GEO_BLOCKED') {
      return {
        message: data.error.message || 'This service is only available in Cambodia.',
        code: data.error.code,
        retryAfterSeconds,
      };
    }
    if (data.error?.code === 'GENERATION_FROZEN') {
      return {
        message: data.error.message || 'Music generation is paused. Try again later.',
        code: data.error.code,
        retryAfterSeconds,
      };
    }
    if (data.error?.message) {
      return { message: data.error.message, code: data.error.code ?? null, retryAfterSeconds };
    }
    if (typeof data.detail === 'string') {
      return { message: data.detail, code: data.error?.code ?? null, retryAfterSeconds };
    }
    if (data.detail && typeof data.detail === 'object' && !Array.isArray(data.detail) && data.detail.message) {
      return { message: data.detail.message, code: data.error?.code ?? null, retryAfterSeconds };
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      if (first?.msg) {
        return { message: first.msg, code: data.error?.code ?? null, retryAfterSeconds };
      }
    }
    if (typeof data.message === 'string') {
      return { message: data.message, code: data.error?.code ?? null, retryAfterSeconds };
    }
  } catch {
    /* ignore */
  }
  return { message: fallback, code: null, retryAfterSeconds: headerRetry };
}

async function rejectResponse(response: Response, fallback: string): Promise<never> {
  const parsed = await readError(response, fallback);
  throw new MusicApiError(parsed.message, response.status, parsed.retryAfterSeconds, parsed.code);
}

async function musicFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    const parsed = await readError(response, `Request failed (${response.status})`);
    let message = parsed.message;
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      const looksLikeGateway = /bad gateway|unprocessable|request failed/i.test(message);
      if (!message || looksLikeGateway) {
        message = 'AI assist is temporarily unavailable. Please try again in a moment.';
      }
    }
    throw new MusicApiError(message, response.status, parsed.retryAfterSeconds, parsed.code);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchWebMusicQuota(): Promise<WebMusicQuota> {
  return musicFetch<WebMusicQuota>('/api/v3/web-music/quota');
}

export async function listWebMusicWorkspaces(): Promise<{ items: WebMusicWorkspace[] }> {
  return musicFetch('/api/v3/web-music/workspaces');
}

export async function createWebMusicWorkspace(name: string): Promise<WebMusicWorkspace> {
  return musicFetch('/api/v3/web-music/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function updateWebMusicWorkspace(
  workspaceId: string,
  name: string,
): Promise<WebMusicWorkspace> {
  return musicFetch(`/api/v3/web-music/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function generateWebMusicStyles(input: {
  style?: string;
  lyrics?: string;
  title?: string;
  description?: string;
  prompt?: string;
}): Promise<{ style: string; credits_charged?: number }> {
  return musicFetch('/api/v3/web-music/generate-styles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      style: input.style ?? '',
      lyrics: (input.lyrics ?? '').slice(0, 400),
      title: input.title ?? '',
      description: input.description ?? '',
      prompt: input.prompt ?? '',
    }),
  });
}

export async function generateWebMusicDraft(prompt: string): Promise<{ lyrics: string; title: string }> {
  return musicFetch('/api/v3/web-music/generate-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
}

export async function generateWebMusic(
  input: WebMusicGenerateInput,
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
  return musicFetch('/api/v3/web-music/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function listWebMusicGenerations(
  limit = 40,
  offset = 0,
  workspaceId?: string,
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (workspaceId) params.set('workspace_id', workspaceId);
  return musicFetch<{ items: WebMusicGeneration[]; total: number }>(
    `/api/v3/web-music/generations?${params.toString()}`,
  );
}

export async function getWebMusicGeneration(id: string): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(`/api/v3/web-music/generations/${id}`);
}

export async function unlockWebMusicPreview(id: string): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}/unlock-preview`,
    { method: 'POST' },
  );
}

export async function updateWebMusicGenerationTitle(
  id: string,
  title: string,
  variant?: string,
): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(`/api/v3/web-music/generations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, ...(variant ? { variant } : {}) }),
  });
}

export async function deleteWebMusicGeneration(id: string): Promise<void> {
  await musicFetch<void>(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}`,
    { method: 'DELETE' },
  );
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function fetchWebMusicClipBlob(id: string, variant: string): Promise<Blob> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/generations/${id}/download?variant=${encodeURIComponent(variant)}`,
  );
  if (!response.ok) {
    await rejectResponse(response, 'Download failed');
  }
  return response.blob();
}

export async function fetchWebMusicClipWavBlob(id: string, variant: string): Promise<Blob> {
  const maxAttempts = 8;
  let lastError = 'WAV download failed';
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await musicAuthFetch(
      `/api/v3/web-music/generations/${id}/download-wav?variant=${encodeURIComponent(variant)}`,
    );
    if (response.ok) {
      return response.blob();
    }
    const parsed = await readError(response, 'WAV download failed');
    lastError = parsed.message;
    const retryable = /not ready yet|try again/i.test(lastError);
    if (!retryable || attempt === maxAttempts - 1) {
      throw new Error(lastError);
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, 2500);
    });
  }
  throw new Error(lastError);
}

export async function fetchWebMusicTimedLyricsBlob(
  id: string,
  variant: string,
  format: 'lrc' | 'srt',
): Promise<Blob> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/generations/${id}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${encodeURIComponent(format)}`,
  );
  if (!response.ok) {
    await rejectResponse(response, 'Timed lyrics download failed');
  }
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
  format: 'lrc' | 'srt',
  filename: string,
): Promise<void> {
  saveBlob(await fetchWebMusicTimedLyricsBlob(id, variant, format), filename);
}
