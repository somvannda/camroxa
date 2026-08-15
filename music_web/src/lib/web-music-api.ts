/** Same-origin music-web generation client. */

export type WebMusicQuota = {
  limit: number;
  used: number;
  remaining: number;
  is_pro?: boolean;
  requires_upgrade?: boolean;
};

export type WebMusicClip = {
  variant: 'ok' | 'alt' | string;
  label: string;
  audio_url: string;
  download_url: string;
  ready: boolean;
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
  clips: WebMusicClip[];
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string;
      error?: { message?: string; details?: { requires_upgrade?: boolean } };
    };
    if (data.error?.message) return data.error.message;
    if (typeof data.detail === 'string') return data.detail;
  } catch {
    /* ignore */
  }
  return fallback;
}

async function musicFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      'X-Portal-Context': 'user',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Request failed (${response.status})`));
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchWebMusicQuota(): Promise<WebMusicQuota> {
  return musicFetch<WebMusicQuota>('/api/v1/web-music/quota');
}

export async function generateWebMusic(input: {
  mode: 'simple' | 'advanced';
  lyrics?: string;
  style?: string;
  title?: string;
  prompt?: string;
  instrumental?: boolean;
  model?: 'V5' | 'V5_5';
}): Promise<{ task_id: string; status: string; title: string; style: string; quota: WebMusicQuota }> {
  return musicFetch('/api/v1/web-music/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function listWebMusicGenerations(limit = 40, offset = 0) {
  return musicFetch<{ items: WebMusicGeneration[]; total: number }>(
    `/api/v1/web-music/generations?limit=${limit}&offset=${offset}`,
  );
}

export async function getWebMusicGeneration(id: string): Promise<WebMusicGeneration> {
  return musicFetch<WebMusicGeneration>(`/api/v1/web-music/generations/${id}`);
}

export async function downloadWebMusicClip(id: string, variant: string, filename: string): Promise<void> {
  const response = await fetch(
    `/api/v1/web-music/generations/${id}/download?variant=${encodeURIComponent(variant)}`,
    { credentials: 'include', headers: { 'X-Portal-Context': 'user' } },
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
