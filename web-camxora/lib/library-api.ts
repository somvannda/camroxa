import { musicAuthFetch } from "@/lib/auth-fetch";

export type WebMusicClip = {
  variant: string;
  label?: string;
  image_url?: string | null;
  audio_url?: string | null;
  download_url?: string | null;
  duration_seconds?: number | null;
  ready?: boolean;
};

export type WebMusicGeneration = {
  id: string;
  title: string;
  style: string;
  lyrics?: string | null;
  model?: string;
  model_label?: string;
  instrumental?: boolean;
  status: string;
  created_at?: string | null;
  error_message?: string | null;
  negative_tags?: string | null;
  vocal_gender?: string | null;
  style_weight?: number | null;
  weirdness_constraint?: number | null;
  audio_weight?: number | null;
  is_preview?: boolean;
  preview_seconds?: number | null;
  clips: WebMusicClip[];
};

export type WebMusicPlaylist = {
  id: string;
  name: string;
  slug?: string;
  description?: string | null;
  is_public: boolean;
  song_count: number;
  updated_at?: string | null;
};

export type LikedTrack = {
  id: string;
  title: string;
  artist_name?: string;
  cover_url?: string | null;
  duration_seconds?: number | null;
  added_at?: string | null;
};

async function fetchJson<T>(path: string): Promise<T> {
  const response = await musicAuthFetch(path);
  if (!response.ok) throw new Error(`Library request failed: ${response.status}`);
  return (await response.json()) as T;
}

export async function fetchGenerations(limit = 50): Promise<WebMusicGeneration[]> {
  const data = await fetchJson<{ items: WebMusicGeneration[] }>(
    `/api/v3/web-music/generations?limit=${limit}`
  );
  return data.items ?? [];
}

export async function fetchPlaylists(): Promise<WebMusicPlaylist[]> {
  const data = await fetchJson<{ items: WebMusicPlaylist[] }>("/api/v3/web-music/playlists");
  return data.items ?? [];
}

export async function fetchLikedTracks(limit = 50): Promise<LikedTrack[]> {
  const data = await fetchJson<{ items: LikedTrack[] }>(
    `/api/v3/streaming/library/likes?limit=${limit}`
  );
  return data.items ?? [];
}
