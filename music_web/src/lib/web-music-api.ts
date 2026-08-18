/** Same-origin music-web generation client. */

import { musicAuthFetch } from '@/lib/auth-fetch';

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
};

export type WebMusicClip = {
  variant: 'ok' | 'alt' | string;
  label: string;
  audio_url: string;
  download_url: string;
  ready: boolean;
  image_url?: string | null;
  duration_seconds?: number | null;
  title?: string;
};

export type WebMusicGeneration = {
  id: string;
  title: string;
  lyrics: string;
  style: string;
  model: string;
  instrumental: boolean;
  status: string;
  error_message?: string | null;
  created_at?: string | null;
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

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?:
        | string
        | { message?: string }
        | Array<{ msg?: string; loc?: Array<string | number> }>;
      error?: { message?: string; code?: string; details?: { requires_upgrade?: boolean } };
      message?: string;
    };
    if (data.error?.message) return data.error.message;
    if (typeof data.detail === 'string') return data.detail;
    if (data.detail && typeof data.detail === 'object' && !Array.isArray(data.detail) && data.detail.message) {
      return data.detail.message;
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      if (first?.msg) return first.msg;
    }
    if (typeof data.message === 'string') return data.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

async function musicFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    const message = await readError(response, `Request failed (${response.status})`);
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      const looksLikeGateway = /bad gateway|unprocessable|request failed/i.test(message);
      throw new Error(
        message && !looksLikeGateway
          ? message
          : 'AI assist is temporarily unavailable. Please try again in a moment.',
      );
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchWebMusicQuota(): Promise<WebMusicQuota> {
  return musicFetch<WebMusicQuota>('/api/v1/web-music/quota');
}

export async function listWebMusicWorkspaces(): Promise<{ items: WebMusicWorkspace[] }> {
  return musicFetch('/api/v1/web-music/workspaces');
}

export async function createWebMusicWorkspace(name: string): Promise<WebMusicWorkspace> {
  return musicFetch('/api/v1/web-music/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
}

export async function updateWebMusicWorkspace(
  workspaceId: string,
  name: string,
): Promise<WebMusicWorkspace> {
  return musicFetch(`/api/v1/web-music/workspaces/${encodeURIComponent(workspaceId)}`, {
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
  return musicFetch('/api/v1/web-music/generate-styles', {
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
  return musicFetch('/api/v1/web-music/generate-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
}

export async function generateWebMusic(input: {
  mode: 'simple' | 'advanced';
  lyrics?: string;
  style?: string;
  title?: string;
  prompt?: string;
  instrumental?: boolean;
  model?: 'V5' | 'V5_5';
  negative_tags?: string;
  vocal_gender?: 'm' | 'f' | 'both';
  style_weight?: number;
  weirdness_constraint?: number;
  audio_weight?: number;
  workspace_id?: string;
}): Promise<{ task_id: string; status: string; title: string; style: string; quota: WebMusicQuota }> {
  return musicFetch('/api/v1/web-music/generate', {
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
    `/api/v1/web-music/generations?${params.toString()}`,
  );
}

export async function getWebMusicGeneration(id: string): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(`/api/v1/web-music/generations/${id}`);
}

export async function updateWebMusicGenerationTitle(
  id: string,
  title: string,
  variant?: string,
): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(`/api/v1/web-music/generations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, ...(variant ? { variant } : {}) }),
  });
}

export async function downloadWebMusicClip(id: string, variant: string, filename: string): Promise<void> {
  const response = await musicAuthFetch(
    `/api/v1/web-music/generations/${id}/download?variant=${encodeURIComponent(variant)}`,
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'Download failed'));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadWebMusicClipWav(id: string, variant: string, filename: string): Promise<void> {
  const maxAttempts = 8;
  let lastError = 'WAV download failed';
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await musicAuthFetch(
      `/api/v1/web-music/generations/${id}/download-wav?variant=${encodeURIComponent(variant)}`,
    );
    if (response.ok) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      return;
    }
    lastError = await readError(response, 'WAV download failed');
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

export async function downloadWebMusicTimedLyrics(
  id: string,
  variant: string,
  format: 'lrc' | 'srt',
  filename: string,
): Promise<void> {
  const response = await musicAuthFetch(
    `/api/v1/web-music/generations/${id}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${encodeURIComponent(format)}`,
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'Timed lyrics download failed'));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
