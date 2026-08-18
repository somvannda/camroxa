/** Web music playlist client. */

import { musicAuthFetch } from '@/lib/auth-fetch';

function resolveApiBase(): string {
  if (typeof window !== 'undefined') return '';
  return (
    process.env.STREAMING_API_BASE_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ||
    process.env.PLATFORM_API_BASE_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

export function getPlaylistApiBase(): string {
  return resolveApiBase();
}

export type WebMusicPlaylist = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_public: boolean;
  song_count: number;
  is_owner?: boolean;
  created_at?: string | null;
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
  audio_url?: string;
  image_url?: string | null;
  added_at?: string | null;
};

export type WebMusicPublicPlaylist = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  song_count: number;
  cover_url?: string | null;
  updated_at?: string | null;
  creator_user_id: string;
  creator_name: string;
  creator_avatar_url?: string | null;
};

export type WebMusicPublicArtist = {
  user_id: string;
  artist_name: string;
  avatar_url?: string | null;
  playlist_count: number;
  album_count?: number;
  track_count: number;
};

export type WebMusicPublicArtistAlbum = {
  id: string;
  album_name: string;
  artist_name?: string;
  user_id: string;
  track_count?: number;
  play_count?: number;
  cover_url?: string | null;
};

export type WebMusicPublicRecentTrack = {
  id: string;
  task_id: string;
  variant: string;
  title: string;
  artist_name: string;
  user_id: string;
  playlist_name?: string;
  style?: string;
  genre?: string | null;
  cover_url?: string | null;
  play_url: string;
  added_at?: string | null;
  play_count?: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.message === 'string') return payload.message;
    if (typeof payload?.detail === 'string') return payload.detail;
  } catch {
    // ignore
  }
  return fallback;
}

async function fetchPublicJson<T>(path: string): Promise<T> {
  const base = resolveApiBase();
  const response = await fetch(`${base}${path}`, {
    credentials: typeof window !== 'undefined' ? 'include' : 'omit',
    ...(typeof window === 'undefined' ? { next: { revalidate: 30 } } : {}),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Request failed: ${response.status}`));
  }
  return response.json() as Promise<T>;
}

export async function listPublicPlaylists(limit = 24, offset = 0): Promise<Paginated<WebMusicPublicPlaylist>> {
  return fetchPublicJson<Paginated<WebMusicPublicPlaylist>>(
    `/api/v1/web-music/public/playlists?limit=${limit}&offset=${offset}`,
  );
}

export async function listPublicArtists(limit = 48, offset = 0): Promise<Paginated<WebMusicPublicArtist>> {
  return fetchPublicJson<Paginated<WebMusicPublicArtist>>(
    `/api/v1/web-music/public/artists?limit=${limit}&offset=${offset}`,
  );
}

export async function listPublicRecentTracks(
  limit = 12,
  offset = 0,
): Promise<Paginated<WebMusicPublicRecentTrack>> {
  return fetchPublicJson<Paginated<WebMusicPublicRecentTrack>>(
    `/api/v1/web-music/public/tracks/recent?limit=${limit}&offset=${offset}`,
  );
}

export async function getPublicArtist(
  userId: string,
): Promise<WebMusicPublicArtist & { playlists: WebMusicPublicPlaylist[]; albums: WebMusicPublicArtistAlbum[] }> {
  return fetchPublicJson<
    WebMusicPublicArtist & { playlists: WebMusicPublicPlaylist[]; albums: WebMusicPublicArtistAlbum[] }
  >(`/api/v1/web-music/public/artists/${encodeURIComponent(userId)}`);
}

export async function listWebMusicPlaylists(): Promise<{ items: WebMusicPlaylist[] }> {
  const response = await musicAuthFetch('/api/v1/web-music/playlists');
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to load playlists'));
  }
  return response.json();
}

export async function createWebMusicPlaylist(input: {
  name: string;
  description?: string;
  is_public?: boolean;
}): Promise<WebMusicPlaylist> {
  const response = await musicAuthFetch('/api/v1/web-music/playlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to create playlist'));
  }
  return response.json();
}

export async function getWebMusicPlaylist(id: string): Promise<WebMusicPlaylist> {
  const response = await musicAuthFetch(`/api/v1/web-music/playlists/${encodeURIComponent(id)}`);
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to load playlist'));
  }
  return response.json();
}

export async function updateWebMusicPlaylist(
  id: string,
  input: { name?: string; description?: string; is_public?: boolean },
): Promise<WebMusicPlaylist> {
  const response = await musicAuthFetch(`/api/v1/web-music/playlists/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to update playlist'));
  }
  return response.json();
}

export async function deleteWebMusicPlaylist(id: string): Promise<void> {
  const response = await musicAuthFetch(`/api/v1/web-music/playlists/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to delete playlist'));
  }
}

export async function listWebMusicPlaylistItems(id: string): Promise<{ items: WebMusicPlaylistItem[] }> {
  const response = await musicAuthFetch(`/api/v1/web-music/playlists/${encodeURIComponent(id)}/items`);
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to load playlist songs'));
  }
  return response.json();
}

export async function addWebMusicPlaylistItem(
  playlistId: string,
  input: { task_id: string; variant?: 'ok' | 'alt' },
): Promise<WebMusicPlaylistItem> {
  const response = await musicAuthFetch(
    `/api/v1/web-music/playlists/${encodeURIComponent(playlistId)}/items`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to add song to playlist'));
  }
  return response.json();
}

export async function removeWebMusicPlaylistItem(playlistId: string, itemId: string): Promise<void> {
  const response = await musicAuthFetch(
    `/api/v1/web-music/playlists/${encodeURIComponent(playlistId)}/items/${encodeURIComponent(itemId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to remove song from playlist'));
  }
}
